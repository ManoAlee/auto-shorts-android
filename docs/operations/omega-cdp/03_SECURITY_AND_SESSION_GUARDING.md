# Diretrizes de Segurança, Guardrails e Gerenciamento de Sessão

## 1. Princípios Inegociáveis de Segurança
O **Omega CDP Control Engine** foi desenvolvido estritamente para gerenciar operações em contas próprias e autorizadas, obedecendo às seguintes invariantes:

1. **Zero Evasão de Segurança:** O sistema **NUNCA** tenta resolver, contornar, quebrar ou burlar CAPTCHAs (reCAPTCHA, hCaptcha, Turnstile, Arkose), verificações biométricas, checagens de dispositivo ou SMS/MFA.
2. **Interrupção Imediata (`REQUIRES_HUMAN_ACTION`):** Se qualquer desafio de segurança humana for detectado na navegação, a tarefa é pausada imediatamente e o operador é notificado.
3. **Isolamento de Credenciais:**
   * Nenhuma senha ou segredo é gravado em texto puro nos arquivos de log.
   * Cookies de sessão são armazenados em diretórios restritos (`output/browser_profiles/<platform>/cookies.json`) com permissões POSIX restritas (`chmod 600` para o arquivo e `chmod 700` para a pasta).
4. **Isolamento Local do Endpoint CDP:**
   * O Chromium escuta **exclusivamente** na interface local `127.0.0.1`.
   * A porta de depuração é escolhida dinamicamente (`_pick_free_port()`) no intervalo efêmero do kernel.
   * É terminantemente proibido expor portas CDP na WAN ou em túneis externos.

---

## 2. Detecção de Desafios Humanos e Verificações de Segurança
O `SecureSessionManager` implementa um scanner passivo sobre a URL e o DOM:

```python
_HUMAN_CHALLENGE_PATTERNS = [
    (r"accounts\.google\.com/.*challenge", "GOOGLE_AUTH_CHALLENGE", "Verificação em duas etapas ou confirmação de dispositivo do Google"),
    (r"tiktok\.com/login", "TIKTOK_LOGIN_REQUIRED", "Sessão do TikTok expirada ou não autenticada"),
    (r"verify-center|security.*challenge", "TIKTOK_CAPTCHA_VERIFY", "Verificação de segurança / puzzle captcha do TikTok"),
    (r"instagram\.com/challenge|checkpoint_required", "INSTAGRAM_CHALLENGE", "Ponto de verificação de segurança do Instagram"),
    (r"challenges\.cloudflare\.com|cf-turnstile", "CLOUDFLARE_CHALLENGE", "Desafio Cloudflare / Verificação de navegador"),
    (r"recaptcha|hcaptcha|arkose", "CAPTCHA_DETECTED", "Desafio de verificação humana detectado na página"),
]
```

Quando um padrão é detectado:
1. O navegador é mantido aberto se estiver em modo visível para que o operador humano conclua o login legítimo.
2. Em modo headless, o processo é encerrado de forma limpa.
3. O status da tarefa é alterado para `REQUIRES_HUMAN_ACTION`, com descrição clara do desafio.
4. Nenhuma tentativa de força bruta ou repetição automatizada é executada.

---

## 3. Prevenção de Travas de Sessão e Limpeza de Órfãos
Para evitar que uma sessão interrompida abruptamente bloqueie futuras execuções:
* O gerenciador valida e remove links simbólicos órfãos (`SingletonLock`, `SingletonSocket`, `SingletonCookie`) antes de cada inicialização.
* Toda sessão iniciada em POSIX utiliza `preexec_fn=os.setsid` e o teardown garantido via `terminate_chromium_process_group`, impedindo o acúmulo de processos filhos em background.
