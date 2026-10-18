//! In-memory fix for the 0.589 client's allocator, applied while the game is still suspended.
//!
//! The client's memory manager gives every allocating thread one of 64 per-thread heap slots
//! (`unk_145347ED0`). It sizes its thread pools from the CPU count, so on machines with many
//! hardware threads more than 64 threads allocate. A thread that gets no slot never caches one, and
//! on *every* allocation `sub_142B6B7F0` rescans all 64 slots, calling OpenThread /
//! GetExitCodeThread / GetProcessIdOfThread / CloseHandle for each, under the global allocator
//! lock. Every other thread (the main thread included) queues behind it: the window stops
//! responding and terrain loading never finishes.
//!
//! The patch turns that rescan into "no slot": the thread falls back to the shared allocator path,
//! which is cheap. Slots released by exiting threads are still reused through the free-slot scan
//! that runs before it. The game file on disk is not modified.

use std::process::{Child, Command};

/// `sub_142B6B7F0` at the start of the full-table rescan, image base 0x140000000.
const PATCH_RVA: usize = 0x2B6_B8C1;
/// `mov rdi, rsi` - only present at this offset in client 0.589.1.128895.
const ORIGINAL: [u8; 3] = [0x48, 0x8B, 0xFE];
/// `jmp short 0x142B6B939` (unlock and return the null slot in rsi), `nop`.
const PATCHED: [u8; 3] = [0xEB, 0x76, 0x90];

pub enum PatchOutcome {
    Applied,
    /// Different client build; started unmodified.
    NotApplicable,
}

/// Starts `command` suspended, patches it when it is the 0.589 client, then resumes it.
#[cfg(windows)]
pub fn spawn_patched(command: &mut Command) -> Result<(Child, PatchOutcome), String> {
    use std::os::windows::process::CommandExt;

    const CREATE_SUSPENDED: u32 = 0x4;
    let mut child = command.creation_flags(CREATE_SUSPENDED).spawn().map_err(|e| e.to_string())?;
    let result = win::patch(&child);
    if let Err(e) = win::resume(&child) {
        let _ = child.kill();
        return Err(format!("could not resume the game: {e}"));
    }
    match result {
        Ok(outcome) => Ok((child, outcome)),
        Err(e) => {
            eprintln!("Allocator fix not applied: {e}");
            Ok((child, PatchOutcome::NotApplicable))
        }
    }
}

#[cfg(not(windows))]
pub fn spawn_patched(command: &mut Command) -> Result<(Child, PatchOutcome), String> {
    let child = command.spawn().map_err(|e| e.to_string())?;
    Ok((child, PatchOutcome::NotApplicable))
}

#[cfg(windows)]
mod win {
    use std::ffi::c_void;
    use std::os::windows::io::AsRawHandle;
    use std::process::Child;

    use windows_sys::Win32::Foundation::HANDLE;
    use windows_sys::Win32::System::Diagnostics::Debug::{FlushInstructionCache, ReadProcessMemory, WriteProcessMemory};
    use windows_sys::Win32::System::Memory::{VirtualProtectEx, PAGE_EXECUTE_READWRITE};

    use super::{PatchOutcome, ORIGINAL, PATCHED, PATCH_RVA};

    #[repr(C)]
    struct ProcessBasicInformation {
        exit_status: i32,
        peb_base_address: *mut c_void,
        affinity_mask: usize,
        base_priority: i32,
        unique_process_id: usize,
        inherited_from_unique_process_id: usize,
    }

    #[link(name = "ntdll")]
    extern "system" {
        fn NtQueryInformationProcess(
            process: HANDLE,
            class: u32,
            info: *mut c_void,
            length: u32,
            return_length: *mut u32,
        ) -> i32;
        fn NtResumeProcess(process: HANDLE) -> i32;
    }

    fn read(process: HANDLE, address: usize, buffer: &mut [u8]) -> Result<(), String> {
        let mut done = 0;
        let ok = unsafe {
            ReadProcessMemory(process, address as *const c_void, buffer.as_mut_ptr().cast(), buffer.len(), &mut done)
        };
        if ok == 0 || done != buffer.len() {
            return Err(format!("ReadProcessMemory({address:#x}) failed"));
        }
        Ok(())
    }

    /// Image base of the (suspended) process, from its PEB.
    fn image_base(process: HANDLE) -> Result<usize, String> {
        let mut info: ProcessBasicInformation = unsafe { std::mem::zeroed() };
        let status = unsafe {
            NtQueryInformationProcess(
                process,
                0, // ProcessBasicInformation
                (&mut info as *mut ProcessBasicInformation).cast(),
                std::mem::size_of::<ProcessBasicInformation>() as u32,
                std::ptr::null_mut(),
            )
        };
        if status < 0 {
            return Err(format!("NtQueryInformationProcess failed: {status:#x}"));
        }
        let mut base = [0u8; 8];
        read(process, info.peb_base_address as usize + 0x10, &mut base)?; // PEB.ImageBaseAddress
        Ok(usize::from_le_bytes(base))
    }

    pub fn patch(child: &Child) -> Result<PatchOutcome, String> {
        let process = child.as_raw_handle() as HANDLE;
        let address = image_base(process)? + PATCH_RVA;

        let mut current = [0u8; 3];
        read(process, address, &mut current)?;
        if current != ORIGINAL {
            return Ok(PatchOutcome::NotApplicable);
        }

        let mut old_protect = 0;
        let target = address as *const c_void;
        unsafe {
            if VirtualProtectEx(process, target, PATCHED.len(), PAGE_EXECUTE_READWRITE, &mut old_protect) == 0 {
                return Err("VirtualProtectEx failed".into());
            }
            let mut written = 0;
            let ok = WriteProcessMemory(process, target, PATCHED.as_ptr().cast(), PATCHED.len(), &mut written);
            VirtualProtectEx(process, target, PATCHED.len(), old_protect, &mut old_protect);
            if ok == 0 || written != PATCHED.len() {
                return Err("WriteProcessMemory failed".into());
            }
            FlushInstructionCache(process, target, PATCHED.len());
        }
        Ok(PatchOutcome::Applied)
    }

    pub fn resume(child: &Child) -> Result<(), String> {
        let status = unsafe { NtResumeProcess(child.as_raw_handle() as HANDLE) };
        if status < 0 {
            return Err(format!("NtResumeProcess failed: {status:#x}"));
        }
        Ok(())
    }

    /// Patches a real client without ever running it: `LANDMARK_EXE=<path to Landmark64.exe>
    /// cargo test -- --ignored`.
    #[test]
    #[ignore]
    fn patches_suspended_client() {
        use std::os::windows::process::CommandExt;

        let exe = std::env::var("LANDMARK_EXE").expect("set LANDMARK_EXE");
        let mut child = std::process::Command::new(exe).creation_flags(0x4).spawn().unwrap();
        let outcome = patch(&child);
        let process = child.as_raw_handle() as HANDLE;
        let mut now = [0u8; 3];
        let read_back = image_base(process).and_then(|base| read(process, base + PATCH_RVA, &mut now));
        child.kill().unwrap();

        assert!(matches!(outcome, Ok(PatchOutcome::Applied)), "patch was not applied");
        read_back.unwrap();
        assert_eq!(now, PATCHED);
    }
}
