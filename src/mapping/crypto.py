# ============================================================
# src/mapping/crypto.py
# Criptografia AES-256-CBC para os HTMLs do mapa.
# ============================================================

import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.backends import default_backend


def _derivar_chave(senha: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
        backend=default_backend(),
    )
    return kdf.derive(senha.encode("utf-8"))


def _criptografar_aes(chave: bytes, iv: bytes, conteudo: bytes) -> bytes:
    padder = padding.PKCS7(128).padder()
    conteudo_padded = padder.update(conteudo) + padder.finalize()
    cipher = Cipher(algorithms.AES(chave), modes.CBC(iv), backend=default_backend())
    enc = cipher.encryptor()
    return enc.update(conteudo_padded) + enc.finalize()


def _template_html(conteudo_b64: str, salt_b64: str, iv_b64: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Fugini — Mapa São Carlos</title>
  <style>
    body {{ font-family: 'Segoe UI', sans-serif; background: #f0f2f5;
           display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
    .card {{ background: white; border-radius: 12px; padding: 40px;
             width: 100%; max-width: 340px; box-shadow: 0 4px 24px rgba(0,0,0,0.10); }}
    h2 {{ color: #1a1a2e; font-size: 20px; margin-bottom: 4px; }}
    p  {{ color: #888; font-size: 13px; margin-bottom: 20px; }}
    input {{ width: 100%; padding: 10px 14px; border: 1.5px solid #ddd;
             border-radius: 8px; font-size: 14px; margin-bottom: 14px;
             outline: none; box-sizing: border-box; }}
    input:focus {{ border-color: #e74c3c; }}
    button {{ width: 100%; padding: 12px; background: #e74c3c; color: white;
              border: none; border-radius: 8px; font-size: 15px; font-weight: 600;
              cursor: pointer; }}
    button:hover {{ background: #c0392b; }}
    .erro {{ display: none; margin-top: 12px; padding: 10px; background: #fdecea;
             border-radius: 8px; color: #c0392b; font-size: 13px; text-align: center; }}
    .carregando {{ display: none; text-align: center; color: #888; font-size: 13px; }}
  </style>
</head>
<body>
  <div class="card" id="card-login">
    <h2>Fugini Alimentos</h2>
    <p>Mapa de Clientes — São Carlos e Região</p>
    <input type="password" id="senha" placeholder="Senha" autocomplete="current-password">
    <button onclick="descriptografar()">Entrar</button>
    <div class="erro" id="erro">Senha incorreta.</div>
  </div>
  <div class="card carregando" id="card-carregando">
    <p style="margin:0;">Carregando mapa...</p>
  </div>
  <script>
    const CONTEUDO_B64 = "{conteudo_b64}";
    const SALT_B64     = "{salt_b64}";
    const IV_B64       = "{iv_b64}";

    function b64ToBytes(b64) {{
      const bin = atob(b64);
      const arr = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
      return arr;
    }}

    async function descriptografar() {{
      const senha = document.getElementById('senha').value.trim();
      const erro  = document.getElementById('erro');
      erro.style.display = 'none';
      try {{
        const enc    = new TextEncoder();
        const keyMat = await crypto.subtle.importKey("raw", enc.encode(senha), "PBKDF2", false, ["deriveKey"]);
        const chave  = await crypto.subtle.deriveKey(
          {{ name: "PBKDF2", salt: b64ToBytes(SALT_B64), iterations: 100000, hash: "SHA-256" }},
          keyMat, {{ name: "AES-CBC", length: 256 }}, false, ["decrypt"]
        );
        const dec  = await crypto.subtle.decrypt({{ name: "AES-CBC", iv: b64ToBytes(IV_B64) }}, chave, b64ToBytes(CONTEUDO_B64));
        const html = new TextDecoder().decode(dec);
        document.open(); document.write(html); document.close();
      }} catch(e) {{ erro.style.display = 'block'; }}
    }}

    document.getElementById('senha').addEventListener('keydown', e => {{ if (e.key === 'Enter') descriptografar(); }});

    // Auto-login: se a URL tem #senha, usa automaticamente sem exigir digitação
    (function() {{
      const hash = window.location.hash.substring(1); // remove o '#'
      if (hash) {{
        document.getElementById('card-login').style.display = 'none';
        document.getElementById('card-carregando').style.display = 'block';
        document.getElementById('senha').value = decodeURIComponent(hash);
        descriptografar();
      }}
    }})();
  </script>
</body>
</html>"""


def criptografar_html(path_input: Path, path_output: Path, senha: str):
    conteudo = path_input.read_bytes()
    salt     = os.urandom(16)
    iv       = os.urandom(16)
    chave    = _derivar_chave(senha, salt)
    cifrado  = _criptografar_aes(chave, iv, conteudo)

    conteudo_b64 = base64.b64encode(cifrado).decode("ascii")
    salt_b64     = base64.b64encode(salt).decode("ascii")
    iv_b64       = base64.b64encode(iv).decode("ascii")

    path_output.write_text(_template_html(conteudo_b64, salt_b64, iv_b64), encoding="utf-8")
