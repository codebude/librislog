import{c as a,Q as n,j as e,m as i}from"./chunks/framework.BOkOGOZz.js";const t="/screenshots/profile-api-keys.png",k=JSON.parse('{"title":"API Documentation","description":"","frontmatter":{},"headers":[],"relativePath":"api/index.md","filePath":"api/index.md","lastUpdated":1787636109000}'),p={name:"api/index.md"};function o(l,s,r,c,d,h){return n(),e("div",null,[...s[0]||(s[0]=[i('<h1 id="api-documentation" tabindex="-1">API Documentation <a class="header-anchor" href="#api-documentation" aria-label="Permalink to &quot;API Documentation&quot;">​</a></h1><p>LibrisLog provides a full REST API with interactive documentation.</p><h2 id="interactive-api-docs" tabindex="-1">Interactive API Docs <a class="header-anchor" href="#interactive-api-docs" aria-label="Permalink to &quot;Interactive API Docs&quot;">​</a></h2><p>Two documentation interfaces are available when the backend is running:</p><ul><li><strong>Swagger UI</strong>: <code>http://localhost:8000/api/docs</code></li><li><strong>ReDoc</strong>: <code>http://localhost:8000/api/redoc</code></li></ul><p>The OpenAPI schema is also available at:</p><ul><li><strong>JSON</strong>: <code>http://localhost:8000/api/openapi.json</code></li></ul><h2 id="authentication" tabindex="-1">Authentication <a class="header-anchor" href="#authentication" aria-label="Permalink to &quot;Authentication&quot;">​</a></h2><p>All API endpoints (except health check and documentation) require authentication via an API key.</p><h3 id="creating-an-api-key" tabindex="-1">Creating an API Key <a class="header-anchor" href="#creating-an-api-key" aria-label="Permalink to &quot;Creating an API Key&quot;">​</a></h3><ol><li>Log in to the web application</li><li>Go to your Profile page</li><li>Scroll to the &quot;API Keys&quot; section</li><li>Click &quot;Create API Key&quot;</li><li>Enter a description (optional)</li><li>Copy the key immediately — it is shown only once</li></ol><p><img src="'+t+`" alt="API Keys" loading="lazy"></p><h3 id="using-an-api-key" tabindex="-1">Using an API Key <a class="header-anchor" href="#using-an-api-key" aria-label="Permalink to &quot;Using an API Key&quot;">​</a></h3><p>Include the key in the <code>X-API-Key</code> header with every request:</p><div class="language-bash vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">bash</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;">curl</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> -H</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> &quot;X-API-Key: YOUR_KEY_HERE&quot;</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> http://localhost:8000/api/books</span></span></code></pre></div><h3 id="example-request" tabindex="-1">Example Request <a class="header-anchor" href="#example-request" aria-label="Permalink to &quot;Example Request&quot;">​</a></h3><div class="language-bash vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">bash</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#6A737D;--shiki-dark:#6A737D;"># List all books</span></span>
<span class="line"><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;">curl</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> -H</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> &quot;X-API-Key: YOUR_KEY_HERE&quot;</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> \\</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">  http://localhost:8000/api/books</span></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#6A737D;--shiki-dark:#6A737D;"># Create a new book</span></span>
<span class="line"><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;">curl</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> -X</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> POST</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> \\</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  -H</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> &quot;X-API-Key: YOUR_KEY_HERE&quot;</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> \\</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  -H</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> &quot;Content-Type: application/json&quot;</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> \\</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  -d</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> &#39;{&quot;title&quot;: &quot;The Great Gatsby&quot;, &quot;authors&quot;: [&quot;F. Scott Fitzgerald&quot;]}&#39;</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> \\</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">  http://localhost:8000/api/books</span></span></code></pre></div><h3 id="book-author-fields" tabindex="-1">Book author fields <a class="header-anchor" href="#book-author-fields" aria-label="Permalink to &quot;Book author fields&quot;">​</a></h3><p>Book responses contain two author fields:</p><ul><li><code>author</code> — <strong>deprecated</strong>. The <strong>joined</strong> string of all authors (e.g. <code>&quot;Neil Gaiman, Terry Pratchett&quot;</code>). Kept for backward compatibility with existing consumers; use <code>authors</code> instead.</li><li><code>authors</code> — the <strong>list</strong> of individual author names (e.g. <code>[&quot;Neil Gaiman&quot;, &quot;Terry Pratchett&quot;]</code>).</li></ul><p>The <code>author</code> field is marked as <strong>deprecated</strong> in the OpenAPI spec (visible in Swagger UI) on all book schemas. It still works but may be removed in a future release.</p><p>When creating a book you must provide at least one author — either <code>authors</code> as a list, or the legacy <code>author</code> string. If both are sent, <code>authors</code> takes precedence. A request with neither (or with an empty <code>authors</code> list) is rejected with a <code>422</code> validation error.</p><p>For updates, <code>author</code>/<code>authors</code> are optional; if you send an empty <code>authors</code> list the book&#39;s authors are cleared.</p><p>The legacy <code>author</code> string is <strong>parsed on commas, tag-style</strong> (e.g. <code>&quot;Isaac Asimov, Frank Herbert&quot;</code> becomes two authors). This only applies to the API create/update path. It differs from <strong>file import</strong> (CSV/JSON), where a single author string is split on <code>;</code>, <code>&amp;</code>, or <code>and</code> — never on commas — so a name like <code>&quot;Asimov, Isaac&quot;</code> stays one author. See <a href="./../guide/using-librislog/import-export.html">Import &amp; Export</a> for the import behaviour.</p><h1 id="update-reading-status" tabindex="-1">Update reading status <a class="header-anchor" href="#update-reading-status" aria-label="Permalink to &quot;Update reading status&quot;">​</a></h1><p>curl -X POST <br> -H &quot;X-API-Key: YOUR_KEY_HERE&quot; <br> -H &quot;Content-Type: application/json&quot; <br> -d &#39;{&quot;new_status&quot;: &quot;read&quot;}&#39; <br><a href="http://localhost:8000/api/books/1/transition-status" target="_blank" rel="noreferrer">http://localhost:8000/api/books/1/transition-status</a></p><div class="language- vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang"></span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span></span></span>
<span class="line"><span>## Key Endpoints</span></span>
<span class="line"><span></span></span>
<span class="line"><span>### Books</span></span>
<span class="line"><span></span></span>
<span class="line"><span>| Method | Endpoint | Description |</span></span>
<span class="line"><span>|--------|----------|-------------|</span></span>
<span class="line"><span>| GET | \`/api/books\` | List all books |</span></span>
<span class="line"><span>| POST | \`/api/books\` | Create a book |</span></span>
<span class="line"><span>| GET | \`/api/books/{id}\` | Get book details |</span></span>
<span class="line"><span>| PUT | \`/api/books/{id}\` | Update book |</span></span>
<span class="line"><span>| DELETE | \`/api/books/{id}\` | Delete book |</span></span>
<span class="line"><span>| POST | \`/api/books/{id}/transition-status\` | Change reading status |</span></span>
<span class="line"><span></span></span>
<span class="line"><span>### Progress</span></span>
<span class="line"><span></span></span>
<span class="line"><span>| Method | Endpoint | Description |</span></span>
<span class="line"><span>|--------|----------|-------------|</span></span>
<span class="line"><span>| GET | \`/api/books/{id}/progress\` | List progress entries |</span></span>
<span class="line"><span>| POST | \`/api/books/{id}/progress\` | Add progress entry |</span></span>
<span class="line"><span>| PATCH | \`/api/books/{id}/progress/{entry_id}\` | Update progress date |</span></span>
<span class="line"><span>| DELETE | \`/api/books/{id}/progress/{entry_id}\` | Delete progress entry |</span></span>
<span class="line"><span></span></span>
<span class="line"><span>### Statistics</span></span>
<span class="line"><span></span></span>
<span class="line"><span>| Method | Endpoint | Description |</span></span>
<span class="line"><span>|--------|----------|-------------|</span></span>
<span class="line"><span>| GET | \`/api/statistics\` | Full statistics |</span></span>
<span class="line"><span>| GET | \`/api/statistics/pages-per-day\` | Daily page breakdown |</span></span>
<span class="line"><span></span></span>
<span class="line"><span>### Data Import/Export</span></span>
<span class="line"><span></span></span>
<span class="line"><span>| Method | Endpoint | Description |</span></span>
<span class="line"><span>|--------|----------|-------------|</span></span>
<span class="line"><span>| POST | \`/api/data/export\` | Export data |</span></span>
<span class="line"><span>| POST | \`/api/data/import/parse\` | Parse import file |</span></span>
<span class="line"><span>| POST | \`/api/data/import/validate\` | Validate import |</span></span>
<span class="line"><span>| POST | \`/api/data/import/execute\` | Execute import |</span></span>
<span class="line"><span></span></span>
<span class="line"><span>### Book Import (External Sources)</span></span>
<span class="line"><span></span></span>
<span class="line"><span>| Method | Endpoint | Description |</span></span>
<span class="line"><span>|--------|----------|-------------|</span></span>
<span class="line"><span>| GET | \`/api/import/search\` | Search external sources |</span></span>
<span class="line"><span>| GET | \`/api/import/search/stream\` | Stream search progress |</span></span>
<span class="line"><span>| POST | \`/api/import\` | Import a candidate |</span></span>
<span class="line"><span></span></span>
<span class="line"><span>### Authentication</span></span>
<span class="line"><span></span></span>
<span class="line"><span>| Method | Endpoint | Description |</span></span>
<span class="line"><span>|--------|----------|-------------|</span></span>
<span class="line"><span>| POST | \`/api/auth/setup\` | Create first admin (only when no admin exists) |</span></span>
<span class="line"><span>| POST | \`/api/auth/login\` | Log in with email and password |</span></span>
<span class="line"><span>| POST | \`/api/auth/logout\` | Log out (clear session) |</span></span>
<span class="line"><span>| GET | \`/api/auth/me\` | Get current user |</span></span>
<span class="line"><span>| GET | \`/api/auth/csrf\` | Get CSRF token |</span></span>
<span class="line"><span>| POST | \`/api/auth/forgot-password\` | Request a password reset email (always returns 200) |</span></span>
<span class="line"><span>| POST | \`/api/auth/reset-password\` | Reset password using a token from the reset email |</span></span>
<span class="line"><span></span></span>
<span class="line"><span>::: details Password Reset Endpoints</span></span>
<span class="line"><span>These endpoints do not require an API key or session — they are public.</span></span>
<span class="line"><span></span></span>
<span class="line"><span>**Forgot Password**</span></span>
<span class="line"><span></span></span>
<span class="line"><span>\`\`\`bash</span></span>
<span class="line"><span>curl -X POST http://localhost:8000/api/auth/forgot-password \\</span></span>
<span class="line"><span>  -H &quot;Content-Type: application/json&quot; \\</span></span>
<span class="line"><span>  -d &#39;{&quot;email&quot;: &quot;user@example.com&quot;, &quot;locale&quot;: &quot;en&quot;}&#39;</span></span></code></pre></div><p>Always returns <code>200</code> with <code>{&quot;message&quot;: &quot;If the email is registered, a reset link has been sent&quot;}</code> to prevent user enumeration. The <code>locale</code> field is optional (defaults to <code>en</code>) and controls the email language.</p><p><strong>Reset Password</strong></p><div class="language-bash vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">bash</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;">curl</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> -X</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> POST</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> http://localhost:8000/api/auth/reset-password</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> \\</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  -H</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> &quot;Content-Type: application/json&quot;</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> \\</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  -d</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> &#39;{&quot;token&quot;: &quot;token-from-email&quot;, &quot;password&quot;: &quot;new-secure-password&quot;}&#39;</span></span></code></pre></div><p>Returns <code>200</code> on success, <code>400</code> if the token is invalid/expired or the password doesn&#39;t meet complexity requirements. After a successful reset, all existing sessions for that user are invalidated. :::</p><h2 id="error-handling" tabindex="-1">Error Handling <a class="header-anchor" href="#error-handling" aria-label="Permalink to &quot;Error Handling&quot;">​</a></h2><p>The API returns standard HTTP status codes:</p><ul><li><code>200</code> — Success</li><li><code>201</code> — Created</li><li><code>204</code> — No content (delete success)</li><li><code>400</code> — Bad request</li><li><code>401</code> — Unauthorized (missing or invalid API key)</li><li><code>404</code> — Not found</li><li><code>409</code> — Conflict (e.g., duplicate ISBN)</li><li><code>422</code> — Validation error</li></ul><p>Error responses include a JSON body with details:</p><div class="language-json vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">json</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">{</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;detail&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;Book not found&quot;</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">}</span></span></code></pre></div>`,36)])])}const g=a(p,[["render",o]]);export{k as __pageData,g as default};
