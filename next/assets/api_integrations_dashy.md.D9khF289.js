import{c as a,Q as i,j as n,m as t}from"./chunks/framework.DVP2LVsd.js";const l="/next/screenshots/integrations-dashy.png",F=JSON.parse('{"title":"Dashy","description":"","frontmatter":{},"headers":[],"relativePath":"api/integrations/dashy.md","filePath":"api/integrations/dashy.md","lastUpdated":1781034068000}'),e={name:"api/integrations/dashy.md"};function p(h,s,r,k,d,o){return i(),n("div",null,[...s[0]||(s[0]=[t(`<h1 id="dashy" tabindex="-1">Dashy <a class="header-anchor" href="#dashy" aria-label="Permalink to &quot;Dashy&quot;">​</a></h1><p>LibrisLog can be integrated into <a href="https://dashy.to/" target="_blank" rel="noreferrer">Dashy</a>, a self-hosted dashboard for your services, using its <a href="https://dashy.to/docs/widgets#html-embedded-widget" target="_blank" rel="noreferrer">HTML embedded widget</a>.</p><p>This widget displays your reading statistics as styled stat cards directly on your Dashy dashboard.</p><h2 id="prerequisites" tabindex="-1">Prerequisites <a class="header-anchor" href="#prerequisites" aria-label="Permalink to &quot;Prerequisites&quot;">​</a></h2><ul><li>A running LibrisLog instance reachable from your Dashy server</li><li>An <a href="/next/api/integrations/#api-keys">API key</a> with access to the statistics endpoint</li><li><strong>CORS must be configured</strong> — add your Dashy URL to the <a href="/next/guide/configuration.html#core-settings"><code>CORS_ORIGINS</code></a> environment variable of the LibrisLog backend so that the browser can fetch the API directly</li></ul><h2 id="configuration" tabindex="-1">Configuration <a class="header-anchor" href="#configuration" aria-label="Permalink to &quot;Configuration&quot;">​</a></h2><p>Add the following to the Dashy <code>conf.yml</code> under the section or item where you want the widget to appear:</p><div class="language-yaml vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">yaml</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#22863A;--shiki-dark:#85E89D;">widgets</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">:</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">  - </span><span style="--shiki-light:#22863A;--shiki-dark:#85E89D;">type</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">embed</span></span>
<span class="line"><span style="--shiki-light:#22863A;--shiki-dark:#85E89D;">    updateInterval</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">300</span></span>
<span class="line"><span style="--shiki-light:#22863A;--shiki-dark:#85E89D;">    options</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">:</span></span>
<span class="line"><span style="--shiki-light:#22863A;--shiki-dark:#85E89D;">      html</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">|</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">        &lt;div class=&quot;librislog-widget&quot;&gt;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          &lt;div class=&quot;ll-stat-item&quot;&gt;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            &lt;span class=&quot;ll-label&quot;&gt;Reading&lt;/span&gt;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            &lt;span class=&quot;ll-value&quot; id=&quot;ll-reading&quot;&gt;-&lt;/span&gt;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          &lt;/div&gt;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          &lt;div class=&quot;ll-stat-item&quot;&gt;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            &lt;span class=&quot;ll-label&quot;&gt;Read&lt;/span&gt;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            &lt;span class=&quot;ll-value&quot; id=&quot;ll-read&quot;&gt;-&lt;/span&gt;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          &lt;/div&gt;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          &lt;div class=&quot;ll-stat-item&quot;&gt;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            &lt;span class=&quot;ll-label&quot;&gt;Want to Read&lt;/span&gt;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            &lt;span class=&quot;ll-value&quot; id=&quot;ll-wtr&quot;&gt;-&lt;/span&gt;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          &lt;/div&gt;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          &lt;div class=&quot;ll-stat-item&quot;&gt;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            &lt;span class=&quot;ll-label&quot;&gt;Total Books&lt;/span&gt;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            &lt;span class=&quot;ll-value&quot; id=&quot;ll-total&quot;&gt;-&lt;/span&gt;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          &lt;/div&gt;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">        &lt;/div&gt;</span></span>
<span class="line"><span style="--shiki-light:#22863A;--shiki-dark:#85E89D;">      css</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">|</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">        .librislog-widget {</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          display: grid;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          grid-template-columns: repeat(2, 1fr);</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          gap: 0.75rem;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          padding: 0.5rem;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          font-family: inherit;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">        }</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">        .ll-stat-item {</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          display: flex;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          flex-direction: column;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          align-items: center;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          justify-content: center;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          background: var(--background-elevated, rgba(255,255,255,0.05));</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          border: 1px solid var(--outline-color, rgba(255,255,255,0.1));</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          border-radius: 6px;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          padding: 0.5rem;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          text-align: center;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">        }</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">        .ll-label {</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          font-size: 0.8rem;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          opacity: 0.7;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          color: var(--text-color, #fff);</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          margin-bottom: 0.25rem;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          text-transform: uppercase;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          letter-spacing: 0.05em;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">        }</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">        .ll-value {</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          font-size: 1.4rem;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          font-weight: bold;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          color: var(--primary, #00bc8c);</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">        }</span></span>
<span class="line"><span style="--shiki-light:#22863A;--shiki-dark:#85E89D;">      script</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">|</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">        (async function() {</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          const apiUrl = &#39;&lt;LIBRISLOG-URL&gt;/api/books/stats&#39;;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          const apiKey = &#39;&lt;API-KEY&gt;&#39;;</span></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          try {</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            const response = await fetch(apiUrl, {</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">              method: &#39;GET&#39;,</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">              headers: {</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">                &#39;X-API-Key&#39;: apiKey,</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">                &#39;Content-Type&#39;: &#39;application/json&#39;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">              }</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            });</span></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            if (!response.ok) throw new Error(&#39;API request failed&#39;);</span></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            const data = await response.json();</span></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            document.getElementById(&#39;ll-reading&#39;).innerText = data.books_currently_reading ?? data.books_reading ?? 0;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            document.getElementById(&#39;ll-read&#39;).innerText = data.books_read ?? 0;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            document.getElementById(&#39;ll-wtr&#39;).innerText = data.books_want_to_read ?? 0;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            document.getElementById(&#39;ll-total&#39;).innerText = data.total_books ?? 0;</span></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          } catch (error) {</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            console.error(&#39;LibrisLog Widget Error:&#39;, error);</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            const elements = [&#39;ll-reading&#39;, &#39;ll-read&#39;, &#39;ll-wtr&#39;, &#39;ll-total&#39;];</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            elements.forEach(id =&gt; {</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">              const el = document.getElementById(id);</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">              if (el) el.innerText = &#39;!&#39;;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">              if (el) el.style.color = &#39;var(--danger, #ff0033)&#39;;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">            });</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">          }</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">        })();</span></span></code></pre></div><p>Replace the placeholders with your own values:</p><table tabindex="0"><thead><tr><th>Placeholder</th><th>Example</th><th>Description</th></tr></thead><tbody><tr><td><code>&lt;LIBRISLOG-URL&gt;</code></td><td><code>http://192.168.1.100:8000</code></td><td>The base URL of your LibrisLog instance (http or https)</td></tr><tr><td><code>&lt;API-KEY&gt;</code></td><td><code>lk_nRHsF3jxIBDa9u....</code></td><td>An API key with access to the statistics endpoint</td></tr></tbody></table><p>The <code>updateInterval</code> is specified in seconds. <code>300</code> equals 5 minutes.</p><h2 id="cors" tabindex="-1">CORS <a class="header-anchor" href="#cors" aria-label="Permalink to &quot;CORS&quot;">​</a></h2><p>Since the widget runs inside the Dashy iframe and fetches the LibrisLog API directly from the browser, you must add your Dashy URL to the <a href="/next/guide/configuration.html#core-settings"><code>CORS_ORIGINS</code></a> environment variable of the LibrisLog backend. For example:</p><div class="language- vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang"></span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span>CORS_ORIGINS=[&quot;https://dashy.YOUR-DOMAIN&quot;]</span></span></code></pre></div><h2 id="result" tabindex="-1">Result <a class="header-anchor" href="#result" aria-label="Permalink to &quot;Result&quot;">​</a></h2><p><img src="`+l+'" alt="Dashy Widget" loading="lazy"></p>',16)])])}const g=a(e,[["render",p]]);export{F as __pageData,g as default};
