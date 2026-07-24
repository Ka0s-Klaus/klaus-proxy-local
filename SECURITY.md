# 🔒 Política de Seguridad — Klaus Proxy Local

## 🤔 ¿Qué hago? ¿Cómo lo hago? ¿Y para qué lo hago?

**Qué:** Define cómo reportar vulnerabilidades de seguridad de forma responsable.
**Cómo:** A través de un canal privado, no por Issues públicas.
**Para qué:** Proteger a los usuarios del proyecto mientras se prepara y coordina un fix adecuado.

---

## 📋 Versiones soportadas

| Versión | Soporte de seguridad |
| --- | --- |
| `main` (última) | ✅ Activo |
| Versiones anteriores | ❌ No soportadas |

---

## 🚨 Reportar una vulnerabilidad

> **⚠️ No abras una Issue pública para reportar vulnerabilidades de seguridad.**

Si descubres una vulnerabilidad de seguridad, por favor:

1. **Envía un email** a `security@ka0s-klaus.dev` con:
   - Descripción detallada de la vulnerabilidad
   - Pasos para reproducirla
   - Impacto potencial estimado
   - (Opcional) Propuesta de fix o mitigación

2. **Usa GitHub Private Vulnerability Reporting** si prefieres:
   [Reportar vulnerabilidad](https://github.com/Ka0s-Klaus/klaus-proxy-local/security/advisories/new)

---

## ⏱️ Proceso de respuesta

| Paso | Plazo |
| --- | --- |
| Acuse de recibo | 48 horas |
| Evaluación inicial | 5 días hábiles |
| Fix y comunicación | Según severidad (CVSS) |
| Publicación del advisory | Tras deploy del fix |

---

## 🛡️ Buenas prácticas de seguridad para usuarios

- **Nunca** commitees el contenido de `captures/` ni el vault `.pseudonym_vault.json`: contienen prompts, ficheros en claro y el mapa `real↔seudónimo`. Están en `.gitignore` — mantenlo así.
- **Nunca** hardcodees credenciales. El proxy no persiste API keys; el token del proveedor (`ANTHROPIC_AUTH_TOKEN`) se hereda del entorno del proceso `claude`, no de disco.
- El proxy solo debe escuchar en `127.0.0.1` — no exponerlo a interfaces públicas.
- Mantén las dependencias actualizadas: `pip install --upgrade -r requirements.txt`.

---

## 📄 Scope

Esta política aplica al código en este repositorio. Vulnerabilidades en dependencias deben reportarse a los mantenedores de esas dependencias.
