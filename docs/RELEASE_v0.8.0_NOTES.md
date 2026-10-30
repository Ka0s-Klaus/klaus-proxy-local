# Klaus Proxy Local v0.8.0

**Fecha:** 2026-10-30 · **Anterior:** v0.7.0

Release de **medida**. Ahora puedes saber, proyecto a proyecto, qué datos sensibles tienes, cuáles no cubre el proxy y cuáles han salido ya. `klaus-leak-report` lo resume en un % de cobertura con colores. Para medirlo, `klaus-scan` detecta también **nombres de negocio** (clientes, dominios, IDs cloud) sin revelarlos. Y al medir aparecieron dos huecos reales del proxy, que quedan corregidos.

## ⬆️ Actualizar

```bash
git pull && ./install.sh
```

1. **Reinicia `claude-proxy`. Es imprescindible:** las dos correcciones de seguridad (#142, #148) solo se aplican al arrancar.
2. **Genera tu primer informe de fugas** (en una terminal aparte):

   ```bash
   klaus-leak-report --open
   ```

   La primera vez analiza todas las capturas y tarda varios minutos (unos 9 con ~3.400 capturas y 16 repos), mostrando el progreso. Las siguientes ejecuciones tardan segundos.
3. **Sube la cobertura** aprobando tus nombres de negocio, **en tu terminal**:

   ```bash
   klaus-scan ~/proyectos --reveal
   ```

   Aprueba con `A` los clientes, dominios e IDs que quieras pseudonimizar, salta con `S` el resto y reinicia `claude-proxy`.

> ⚠️ **Cambios de comportamiento**
>
> - **`klaus-scan` ya no muestra los valores.** La salida, `--json` incluido, usa identificadores `⟨categoría·hash·longitud⟩`: `--json` ya no lleva `value` ni `context`. Usa `--reveal` para verlos en claro. Si lo usas en un script, revísalo.
> - **El umbral por defecto de `klaus-scan` es HIGH** (antes CRITICAL), para que se vean los nombres de negocio.
> - **El proxy redacta más credenciales en el contenido** que lee Claude: claves de Anthropic, OpenAI y Stripe, la contraseña de las conexiones y URL, tokens `Bearer`, `refresh_token` y `aws_*`. Claude verá `«REDACTED:…»` en lugar del valor.

`config.json`, la SALT, el vault y las capturas se conservan.

## 🕵️ Informe de fugas por proyecto: `klaus-leak-report` (#146, #150)

Para cada repo git de tu carpeta de proyectos:

| Pregunta | Cómo |
| --- | --- |
| **¿Qué datos sensibles tiene?** | `klaus-scan`: secretos y nombres de negocio |
| **¿Puede sufrir una fuga?** | Cada valor pasa por el pseudonimizador con tus reglas actuales; si sale igual, no está cubierto |
| **¿La ha sufrido?** | Cada captura se atribuye a su proyecto por el directorio de trabajo o los remotes, y se buscan valores reales en `sent/`: tipo, fecha y fichero de captura |
| **Cobertura** | % de valores CRITICAL/HIGH cubiertos. 🟢 ≥ 95 % · 🟡 ≥ 80 % · 🔴 menos, o alguna fuga en los últimos 30 días |

- **Caché** por repo y por captura, que solo guarda identificadores. Se invalida al cambiar tus reglas o el código de Klaus.
- **Valores** como `⟨categoría·hash·longitud⟩`. `--reveal` los muestra en claro.
- **Informe** en `informes/fugas/` (local, no se versiona). El **dashboard de auditoría** añade la tarjeta «🕵️ Fugas por proyecto» con el resumen y un enlace.
- **Las capturas sin proyecto** se separan en conversaciones y el resto del tráfico (telemetría y metadatos, que no llevan directorio de trabajo).

## 🔎 `klaus-scan`: nombres de negocio y salida segura (#140, #152)

**Detecta:**
- razones sociales (`… S.L.`, `… GmbH`, `… Inc.`) y titulares de copyright;
- dominios corporativos de email, de URL y de `git log`, incluido el *tenant* de un SaaS (`cliente.atlassian.net`);
- IDs de GCP, AWS y Azure;
- la identidad de paquete en los manifiestos;
- las claves de incidencias (`PRJ-123`).

Cada valor sale una sola vez, y lo ya protegido solo se cuenta.

**Su salida no revela nada:**
- identificadores con hash en lugar de valores;
- sin contexto;
- las carpetas que comparten una palabra con lo detectado, enmascaradas.

Por eso puedes pedir a Claude Code que lo ejecute. Además:
- `--counts` da solo recuentos;
- sin terminal interactiva ya no falla;
- las conexiones con una contraseña de marcador (`${DB_PASS}`, `{pw}`, `«REDACTED:…»`, `changeme`) ya no cuentan como credencial.

## 🔒 Seguridad

- **Un nombre protegido justo después de una secuencia de escape salía en claro** (#142). En `re.compile(r"\bcliente-x\.es\b")`, la `b` del `\b` iba pegada al nombre y la frontera de palabra no casaba. En la instalación del autor, un nombre de organización protegido había salido así en **107 peticiones**. Ahora `\` + letra cuenta como frontera.
- **El proxy redacta las credenciales que detecta `klaus-scan`** (#148). En las conexiones y URL solo redacta la contraseña: `postgres://app:«REDACTED:url-password»@db/ventas` conserva usuario, host y base de datos. Un test exige que todo lo que `klaus-scan` marca como credencial lo redacte el proxy. En la instalación del autor había **23 contraseñas de `postgres://`** en capturas que salieron en claro.
- **Tu login no se toca.** El proxy solo reescribe el cuerpo de las peticiones: `Authorization` y `x-api-key` salen intactas, y los cuerpos de los endpoints de autenticación (`/v1/oauth/…`, `/api/oauth/token`, `/api/oauth/claude_cli/…`, `/api/auth/…`) pasan sin tocar.

## 🐛 Correcciones

- **`klaus-scan` no protegía lo que aprobabas si `ANTHROPIC_PSEUDO_SALT` no estaba en el entorno** (#156). En una terminal normal, cada aprobación fallaba con «ANTHROPIC_PSEUDO_SALT environment variable is required», y la regla tampoco se añadía a `config.json`. Ahora la SALT se toma de `config.json` (la misma de `claude-proxy`) y la regla se añade antes que el vault. Afecta también a `scripts/add_to_vault.py`.
- **`anthropic-pair-verify` contaba como fuga un seudónimo** (#143). Claude Code cita las rutas ya pseudonimizadas (`/Users/user_1a2b3c4d/…`) y vuelven en el historial. Ahora el verificador ignora los valores con forma de seudónimo, igual que el pseudonimizador. En la instalación del autor eran 356 de 623 pares marcados.

## 🔬 Verificación en la instalación del autor

- **Reproceso de los 623 pares** que el verificador marcaba con fugas, en memoria y con las reglas actuales: con #142 y #143, **los 623 quedan sin fugas**. Del total, 356 eran falsos positivos y 107 la fuga real de #142. Las de nombres de carpeta ya estaban cubiertas.
- **Primer informe de fugas:** 16 proyectos y unas 3.400 capturas. La cobertura global pasa del 59,7 % al 61,5 % con #148; el resto son nombres de negocio pendientes de aprobar.
- **`klaus-scan --counts`** sobre los 16 repos (8.701 ficheros, 3 minutos): la salida solo contiene categorías y cifras.

## 🧪 Calidad

- 833 tests passed, 3 skipped (+87 desde v0.7.0). CI en Python 3.10, 3.11, 3.12 y 3.13.
- Las credenciales de los tests se construyen en tiempo de ejecución, para que los escáneres de secretos no las tomen por reales.

## 📝 Limitaciones conocidas

- **Atribución:** una conversación sin directorio de trabajo ni remotes en la petición no se atribuye a ningún proyecto. El informe la cuenta aparte.
- **Detección de nombres de negocio:** es heurística. Un cliente que solo aparece como palabra suelta, sin forma jurídica, dominio ni manifiesto, no se detecta; añádelo a mano a `pseudo_word_literals`.
- **Lo que ya salió no se recupera.** Las capturas de esas fugas siguen siendo la evidencia hasta que las borre la retención (#132), salvo que las muevas a `captures/archive/`.

**Changelog completo:** [`v0.7.0...v0.8.0`](https://github.com/Ka0s-Klaus/klaus-proxy-local/compare/v0.7.0...v0.8.0) · [CHANGELOG](../CHANGELOG.md)
