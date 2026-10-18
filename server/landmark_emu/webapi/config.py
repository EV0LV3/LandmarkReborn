from __future__ import annotations

from dataclasses import dataclass

from ..shared.config import Configuration


@dataclass
class WebApiConfig:
    enabled: bool = True
    base_uri: str = "http://0.0.0.0:5080"
    # Only needed when base_uri is https.
    certificate_file: str | None = None
    certificate_key_file: str | None = None

    @classmethod
    def bind(cls, config: Configuration, section: str = "WebApi") -> WebApiConfig:
        return cls(
            enabled=config.get_bool(f"{section}:Enabled", True),
            base_uri=config.get_str(f"{section}:BaseURI", "http://0.0.0.0:5080"),
            certificate_file=config.get_str(f"{section}:CertificateFile"),
            certificate_key_file=config.get_str(f"{section}:CertificateKeyFile"),
        )
