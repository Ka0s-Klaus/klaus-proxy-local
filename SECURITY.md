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

- **Nunca** commitees tu `ANTHROPIC_API_KEY` ni ninguna credencial en el repositorio.
- Usa siempre `.env` (incluido en `.gitignore`) para gestionar secretos locales.
- El proxy solo debe escuchar en `127.0.0.1` por defecto — no exponerlo a interfaces públicas sin autenticación.
- Mantén las dependencias actualizadas: `pip install --upgrade -r requirements.txt`.

---

## 📄 Scope

Esta política aplica al código en este repositorio. Vulnerabilidades en dependencias deben reportarse a los mantenedores de esas dependencias.
