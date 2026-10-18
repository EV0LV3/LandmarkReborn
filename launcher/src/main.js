const { invoke } = window.__TAURI__.core;

const $ = (id) => document.getElementById(id);
const loginForm = $("login-form");
const playPanel = $("play-panel");
const status = $("status");

function setStatus(message, kind = "") {
  status.textContent = message ?? "";
  status.className = kind;
}

function render(state) {
  const loggedIn = Boolean(state.username);
  loginForm.hidden = loggedIn;
  playPanel.hidden = !loggedIn;
  $("logged-in-as").textContent = state.username ?? "";
  $("server").textContent = `Server: ${state.server}`;
  $("server").title = `Change "Server" in ${state.configPath}`;
  $("game-path").textContent = state.gamePath ? `Game: ${state.gamePath}` : "Game location not set";
  if (!loggedIn) $("password").value = "";
}

async function busy(button, action) {
  button.disabled = true;
  try {
    return await action();
  } catch (error) {
    setStatus(String(error), "error");
    return undefined;
  } finally {
    button.disabled = false;
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("Logging in…");
  const state = await busy($("login"), () =>
    invoke("login", { username: $("username").value, password: $("password").value }),
  );
  if (state) {
    setStatus("");
    render(state);
    $("play").focus();
  }
});

$("play").addEventListener("click", async () => {
  setStatus("Starting Landmark…");
  const result = await busy($("play"), async () => {
    await invoke("play");
    return true;
  });
  if (result) setStatus("Landmark is starting. Have fun!", "ok");
  render(await invoke("get_state"));
});

$("change-game").addEventListener("click", async () => {
  const state = await busy($("change-game"), () => invoke("select_game"));
  if (state) render(state);
});

$("logout").addEventListener("click", async () => {
  setStatus("");
  render(await invoke("logout"));
  $("username").focus();
});

render(await invoke("get_state"));
$("username").focus();
