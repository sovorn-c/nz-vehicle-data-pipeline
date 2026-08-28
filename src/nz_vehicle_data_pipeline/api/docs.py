# ruff: noqa: E501
"""Branded, dependency-free API documentation page."""

DOCS_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Evidence-first NZ vehicle data API documentation">
  <title>NZ Vehicle Data / API docs</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #17201c;
      --muted: #66716a;
      --line: #d8ddd4;
      --paper: #f4f5ee;
      --surface: #ffffff;
      --deep: #17231f;
      --deep-soft: #22302a;
      --acid: #c8f36a;
      --acid-ink: #18220f;
      --orange: #e87845;
      --code: #101714;
      --shadow: 0 18px 50px rgba(17, 28, 23, .08);
    }

    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font: 15px/1.55 "Avenir Next", "Segoe UI", sans-serif;
    }
    a { color: inherit; }
    button, input { font: inherit; }
    button { cursor: pointer; }
    code, pre, .mono { font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace; }

    .app {
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
      min-height: 100vh;
    }
    .sidebar {
      position: sticky;
      top: 0;
      align-self: start;
      height: 100vh;
      padding: 28px 20px;
      background: var(--deep);
      color: #eaf0e9;
      display: flex;
      flex-direction: column;
      gap: 34px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 11px;
      text-decoration: none;
    }
    .brand-mark {
      display: grid;
      width: 34px;
      height: 34px;
      place-items: center;
      background: var(--acid);
      color: var(--acid-ink);
      font-weight: 900;
      letter-spacing: -.08em;
      transform: rotate(-5deg);
    }
    .brand-copy strong { display: block; font-size: 14px; letter-spacing: -.02em; }
    .brand-copy span { color: #9baa9e; font-size: 11px; }
    .nav-label {
      margin: 0 0 9px 10px;
      color: #829188;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: .16em;
      text-transform: uppercase;
    }
    .nav { display: grid; gap: 3px; }
    .nav a {
      display: block;
      padding: 9px 10px;
      border-radius: 7px;
      color: #b8c4ba;
      font-size: 13px;
      text-decoration: none;
    }
    .nav a:hover, .nav a:focus-visible { background: var(--deep-soft); color: white; outline: none; }
    .sidebar-foot {
      margin-top: auto;
      padding: 14px 10px;
      border: 1px solid #35463d;
      color: #9baa9e;
      font-size: 12px;
    }
    .sidebar-foot strong { display: block; color: var(--acid); font-size: 12px; }

    main { min-width: 0; }
    .topbar {
      position: sticky;
      z-index: 2;
      top: 0;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 16px clamp(20px, 4vw, 62px);
      border-bottom: 1px solid rgba(216, 221, 212, .86);
      background: rgba(244, 245, 238, .92);
      backdrop-filter: blur(12px);
    }
    .crumb { color: var(--muted); font-size: 12px; }
    .crumb b { color: var(--ink); }
    .top-actions { display: flex; align-items: center; gap: 10px; }
    .ready {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 10px;
      color: var(--muted);
      font-size: 12px;
      background: var(--surface);
    }
    .ready::before {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--orange);
      content: "";
    }
    .ready.online::before { background: #5ba247; }
    .openapi-link {
      color: var(--ink);
      font-size: 12px;
      font-weight: 700;
      text-decoration: none;
    }
    .openapi-link:hover { text-decoration: underline; }

    .content { width: min(1180px, 100%); margin: 0 auto; padding: 64px clamp(20px, 4vw, 62px) 90px; }
    .hero { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(280px, .8fr); gap: 42px; align-items: end; padding-bottom: 58px; }
    .eyebrow {
      margin: 0 0 16px;
      color: var(--orange);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: .16em;
      text-transform: uppercase;
    }
    h1, h2, h3 { margin: 0; text-wrap: balance; }
    h1 {
      max-width: 720px;
      font: 500 clamp(44px, 7vw, 86px)/.94 Georgia, "Times New Roman", serif;
      letter-spacing: -.065em;
    }
    .hero-copy { max-width: 620px; margin: 22px 0 0; color: #536059; font-size: 17px; }
    .hero-aside {
      padding: 20px;
      border: 1px solid var(--ink);
      background: var(--deep);
      color: #eaf0e9;
      box-shadow: var(--shadow);
    }
    .hero-aside .mono { color: var(--acid); font-size: 12px; }
    .hero-aside p { margin: 12px 0 0; color: #bcc8be; font-size: 13px; }

    .section { scroll-margin-top: 90px; padding: 38px 0; border-top: 1px solid var(--line); }
    .section-heading { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 20px; }
    .section-heading h2 { font-size: 24px; letter-spacing: -.04em; }
    .section-heading p { max-width: 430px; margin: 0; color: var(--muted); font-size: 13px; }
    .scenario-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
    .scenario {
      min-height: 146px;
      padding: 16px;
      border: 1px solid var(--line);
      background: var(--surface);
      text-align: left;
      transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease;
    }
    .scenario:hover, .scenario:focus-visible { border-color: var(--ink); box-shadow: var(--shadow); transform: translateY(-3px); outline: none; }
    .scenario-tag { color: var(--orange); font-size: 10px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }
    .scenario h3 { margin-top: 20px; font-size: 16px; }
    .scenario p { margin: 5px 0 0; color: var(--muted); font-size: 12px; }
    .scenario code { display: block; margin-top: 15px; overflow: hidden; color: #536059; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }

    .principles { display: grid; grid-template-columns: 1.1fr .9fr; gap: 14px; }
    .principle {
      padding: 22px;
      border: 1px solid var(--line);
      background: var(--surface);
    }
    .principle h3 { font-size: 17px; }
    .principle p { margin: 9px 0 0; color: var(--muted); font-size: 13px; }
    .principle.primary { grid-row: span 2; background: var(--acid); border-color: var(--acid); }
    .principle.primary p { color: #3d4a32; }

    .endpoint-tools { display: flex; align-items: center; gap: 10px; margin-bottom: 18px; }
    .search {
      width: min(360px, 100%);
      border: 1px solid var(--line);
      padding: 10px 12px;
      background: var(--surface);
      color: var(--ink);
      outline: none;
    }
    .search:focus { border-color: var(--ink); box-shadow: 0 0 0 3px rgba(200, 243, 106, .38); }
    .endpoint-count { color: var(--muted); font-size: 12px; }
    .endpoint-group { margin-top: 28px; }
    .endpoint-group h3 { margin-bottom: 9px; font-size: 14px; }
    .endpoint-list { display: grid; gap: 10px; }
    .endpoint {
      overflow: hidden;
      border: 1px solid var(--line);
      background: var(--surface);
    }
    .endpoint summary {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 15px 17px;
      cursor: pointer;
      list-style: none;
    }
    .endpoint summary::-webkit-details-marker { display: none; }
    .endpoint summary:hover { background: #fbfcf8; }
    .method {
      display: inline-grid;
      min-width: 48px;
      padding: 4px 6px;
      place-items: center;
      border-radius: 4px;
      background: var(--acid);
      color: var(--acid-ink);
      font: 800 10px/1 "SFMono-Regular", Consolas, monospace;
    }
    .path { overflow: hidden; font-size: 13px; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
    .summary-text { margin-left: auto; color: var(--muted); font-size: 12px; text-align: right; }
    .endpoint-body { display: grid; grid-template-columns: minmax(0, 1fr) minmax(280px, .8fr); gap: 18px; padding: 0 17px 17px; }
    .endpoint-description { color: var(--muted); font-size: 13px; }
    .endpoint-description p { margin: 0 0 14px; }
    .try-form { display: flex; flex-wrap: wrap; gap: 8px; }
    .param-input {
      min-width: 200px;
      flex: 1;
      border: 1px solid var(--line);
      padding: 9px 10px;
      color: var(--ink);
      background: var(--paper);
    }
    .run, .copy {
      border: 1px solid var(--ink);
      padding: 9px 12px;
      background: var(--ink);
      color: white;
      font-size: 12px;
      font-weight: 700;
    }
    .copy { border-color: var(--line); background: var(--surface); color: var(--ink); }
    .run:hover, .run:focus-visible { background: var(--deep-soft); }
    .copy:hover, .copy:focus-visible { border-color: var(--ink); }
    .response {
      min-height: 105px;
      margin: 0;
      overflow: auto;
      padding: 13px;
      background: var(--code);
      color: #d8e6d5;
      font-size: 11px;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .response[data-state="error"] { color: #ffb39e; }
    .response-label { display: block; margin-bottom: 6px; color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: .1em; }
    .no-results { padding: 15px; border: 1px dashed var(--line); color: var(--muted); font-size: 13px; }

    .footer {
      display: flex;
      justify-content: space-between;
      gap: 20px;
      padding-top: 28px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
    }
    .footer a { color: var(--ink); font-weight: 700; }

    @media (max-width: 980px) {
      .app { grid-template-columns: 1fr; }
      .sidebar { position: static; height: auto; padding: 16px 20px; gap: 15px; }
      .nav-label, .sidebar-foot { display: none; }
      .nav { display: flex; overflow-x: auto; gap: 3px; }
      .nav a { white-space: nowrap; }
      .hero { grid-template-columns: 1fr; }
      .scenario-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 650px) {
      .topbar { align-items: flex-start; flex-direction: column; gap: 8px; }
      .top-actions { width: 100%; justify-content: space-between; }
      .content { padding-top: 40px; }
      h1 { font-size: clamp(42px, 15vw, 68px); }
      .section-heading, .footer { align-items: flex-start; flex-direction: column; }
      .principles { grid-template-columns: 1fr; }
      .principle.primary { grid-row: auto; }
      .endpoint-body { grid-template-columns: 1fr; }
      .endpoint summary { align-items: flex-start; flex-wrap: wrap; }
      .summary-text { width: 100%; margin-left: 60px; text-align: left; }
    }
    @media (prefers-reduced-motion: reduce) {
      html { scroll-behavior: auto; }
      *, *::before, *::after { transition-duration: .01ms !important; animation-duration: .01ms !important; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <a class="brand" href="#top" aria-label="NZ Vehicle Data home">
        <span class="brand-mark">NZ</span>
        <span class="brand-copy"><strong>Vehicle Data</strong><span>API documentation</span></span>
      </a>
      <div>
        <p class="nav-label">Explore</p>
        <nav class="nav" aria-label="Documentation sections">
          <a href="#top">Overview</a>
          <a href="#scenarios">Scenarios</a>
          <a href="#vehicles">Vehicles</a>
          <a href="#evidence">Evidence & audit</a>
          <a href="#system">System</a>
        </nav>
      </div>
      <div class="sidebar-foot"><strong>Evidence first.</strong>Canonical values stay connected to their source observations.</div>
    </aside>

    <main id="top">
      <header class="topbar">
        <div class="crumb"><b>Developer docs</b> / v0.1.0</div>
        <div class="top-actions"><span class="ready" id="ready-status">Checking API…</span><a class="openapi-link" href="/openapi.json">OpenAPI JSON ↗</a></div>
      </header>

      <div class="content">
        <section class="hero" aria-labelledby="page-title">
          <div>
            <p class="eyebrow">NZ Vehicle Data Pipeline</p>
            <h1 id="page-title">Evidence, not guesswork.</h1>
            <p class="hero-copy">A read-only API for canonical vehicle records, source provenance, conflicts, and confidence. Explore the seeded scenarios below, then try any endpoint against the local database.</p>
          </div>
          <div class="hero-aside">
            <span class="mono">GET /v1/vehicles/{vin}</span>
            <p>One canonical view, with the evidence trail still attached. Raw payloads stay on the dedicated observation endpoint.</p>
          </div>
        </section>

        <section class="section" id="scenarios" aria-labelledby="scenarios-title">
          <div class="section-heading"><h2 id="scenarios-title">Start with a scenario</h2><p>Each seeded VIN demonstrates a different reconciliation outcome.</p></div>
          <div class="scenario-grid">
            <button class="scenario" data-vin="1HGCR2F85HA000000" type="button"><span class="scenario-tag">Clean</span><h3>Agreed evidence</h3><p>Dealer + manufacturer + negative risk signals.</p><code>1HGCR2F85HA000000</code></button>
            <button class="scenario" data-vin="1FA6P8CF8H5000000" type="button"><span class="scenario-tag">Risky</span><h3>Positive risk signals</h3><p>Listed, matched, and statutory write-off evidence.</p><code>1FA6P8CF8H5000000</code></button>
            <button class="scenario" data-vin="JM0BL10F000000000" type="button"><span class="scenario-tag">Unknown</span><h3>Unknown stays unknown</h3><p>No negative inference from missing risk evidence.</p><code>JM0BL10F000000000</code></button>
            <button class="scenario" data-vin="WAUZZZ8K7BA000000" type="button"><span class="scenario-tag">Conflict</span><h3>Disagreement stays visible</h3><p>Equal-authority PPSR candidates remain unresolved.</p><code>WAUZZZ8K7BA000000</code></button>
          </div>
        </section>

        <section class="section" id="evidence" aria-labelledby="evidence-title">
          <div class="section-heading"><h2 id="evidence-title">The contract in three ideas</h2><p>Designed for integration work where a plausible answer is not enough.</p></div>
          <div class="principles">
            <article class="principle primary"><h3>Canonical values are projections.</h3><p>Every resolved field points back to supporting observations. Conflicting candidates are recorded before a rule resolves—or refuses to resolve—the field.</p></article>
            <article class="principle"><h3>Confidence measures evidence strength.</h3><p>Scores are deterministic and explainable. They are not a promise of real-world truth.</p></article>
            <article class="principle"><h3>Synthetic data stays labelled.</h3><p>PPSR, stolen, write-off, and dealer records are demonstration fixtures, not official checks.</p></article>
          </div>
        </section>

        <section class="section" id="vehicles" aria-labelledby="vehicles-title">
          <div class="section-heading"><h2 id="vehicles-title">Endpoint explorer</h2><p>Generated from the same OpenAPI document used by clients and tooling.</p></div>
          <div class="endpoint-tools"><label class="mono" for="endpoint-search" style="position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0)">Filter endpoints</label><input class="search" id="endpoint-search" type="search" placeholder="Filter endpoints…"><span class="endpoint-count" id="endpoint-count">Loading endpoints…</span></div>
          <div id="endpoint-list" aria-live="polite"><div class="no-results">Loading the API contract…</div></div>
        </section>

        <section class="section" id="system" aria-labelledby="system-title">
          <div class="section-heading"><h2 id="system-title">Run it locally</h2><p>The release is offline-first, so every example is safe to replay.</p></div>
          <div class="hero-aside"><span class="mono">docker compose up -d --build api</span><p>Then open <a href="/docs" style="color:var(--acid)">localhost:8000/docs</a>. The seed command loads the versioned fixture manifest into PostgreSQL; it does not call live NZTA, NHTSA, PPSR, or Police services.</p></div>
        </section>

        <footer class="footer"><span>NZ Vehicle Data Pipeline · API v0.1.0</span><span><a href="/openapi.json">OpenAPI JSON</a></span></footer>
      </div>
    </main>
  </div>

  <script>
    const examples = {
      vin: '1HGCR2F85HA000000',
      observation_id: 'obs_dealer_feed_dealer_xml_LST_HYUNDAI_02',
      revision_number: '1'
    };
    const endpointRoot = document.getElementById('endpoint-list');
    const search = document.getElementById('endpoint-search');
    const endpointCount = document.getElementById('endpoint-count');
    let operations = [];

    const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
    }[char]));

    const groupFor = (path) => {
      if (path.startsWith('/v1/vehicles')) return 'Vehicles';
      if (path.startsWith('/v1/observations')) return 'Evidence & audit';
      return 'System';
    };

    const renderResponse = (node, status, payload) => {
      node.dataset.state = status >= 400 ? 'error' : 'ok';
      node.textContent = `${status}\n\n${JSON.stringify(payload, null, 2)}`;
    };

    const runRequest = async (button) => {
      const operation = operations[Number(button.dataset.operation)];
      const card = button.closest('.endpoint');
      const response = card.querySelector('.response');
      let path = operation.path;
      card.querySelectorAll('[data-param]').forEach((input) => {
        path = path.replace(`{${input.dataset.param}}`, encodeURIComponent(input.value.trim()));
      });
      response.textContent = 'Requesting…';
      response.dataset.state = 'loading';
      try {
        const result = await fetch(path, { headers: { Accept: 'application/json' } });
        const text = await result.text();
        let payload;
        try { payload = JSON.parse(text); } catch { payload = text; }
        renderResponse(response, result.status, payload);
      } catch (error) {
        renderResponse(response, 0, { error: error.message });
      }
    };

    const copyPath = async (button) => {
      const operation = operations[Number(button.dataset.operation)];
      try {
        await navigator.clipboard.writeText(operation.path);
        const original = button.textContent;
        button.textContent = 'Copied';
        setTimeout(() => { button.textContent = original; }, 1200);
      } catch { button.textContent = 'Copy unavailable'; }
    };

    const renderEndpoints = () => {
      const query = search.value.trim().toLowerCase();
      const visible = operations.filter((operation) => `${operation.path} ${operation.summary} ${groupFor(operation.path)}`.toLowerCase().includes(query));
      endpointCount.textContent = `${visible.length} endpoint${visible.length === 1 ? '' : 's'}`;
      if (!visible.length) {
        endpointRoot.innerHTML = '<div class="no-results">No endpoints match that filter.</div>';
        return;
      }
      const groups = new Map();
      visible.forEach((operation) => {
        if (!groups.has(groupFor(operation.path))) groups.set(groupFor(operation.path), []);
        groups.get(groupFor(operation.path)).push(operation);
      });
      endpointRoot.innerHTML = [...groups.entries()].map(([group, items]) => `
        <div class="endpoint-group" id="${group === 'Vehicles' ? 'vehicles-endpoints' : ''}">
          <h3>${escapeHtml(group)}</h3>
          <div class="endpoint-list">
            ${items.map((operation) => {
              const index = operations.indexOf(operation);
              const params = operation.parameters || [];
              const inputs = params.map((parameter) => `<input class="param-input" data-param="${escapeHtml(parameter.name)}" value="${escapeHtml(examples[parameter.name] || '')}" placeholder="${escapeHtml(parameter.name)}" aria-label="${escapeHtml(parameter.name)}">`).join('');
              return `<details class="endpoint" data-path="${escapeHtml(operation.path)}"><summary><span class="method">GET</span><span class="path mono">${escapeHtml(operation.path)}</span><span class="summary-text">${escapeHtml(operation.summary || 'Read resource')}</span></summary><div class="endpoint-body"><div class="endpoint-description"><p>${escapeHtml(operation.description || operation.summary || 'Read this resource.')}</p><div class="try-form">${inputs}<button class="run" type="button" data-operation="${index}">Try request</button><button class="copy" type="button" data-copy-operation="${index}">Copy path</button></div></div><div><span class="response-label">Response</span><pre class="response">Run a request to inspect the response.</pre></div></div></details>`;
            }).join('')}
          </div>
        </div>`).join('');
      endpointRoot.querySelectorAll('.run').forEach((button) => button.addEventListener('click', () => runRequest(button)));
      endpointRoot.querySelectorAll('[data-copy-operation]').forEach((button) => button.addEventListener('click', () => copyPath(button)));
    };

    const loadContract = async () => {
      try {
        const response = await fetch('/openapi.json');
        const schema = await response.json();
        operations = Object.entries(schema.paths).flatMap(([path, methods]) => Object.entries(methods).filter(([method]) => method === 'get').map(([, operation]) => ({ ...operation, path })));
        renderEndpoints();
      } catch (error) {
        endpointCount.textContent = 'Unavailable';
        endpointRoot.innerHTML = `<div class="no-results">Could not load the OpenAPI contract: ${escapeHtml(error.message)}</div>`;
      }
    };

    const checkReady = async () => {
      const status = document.getElementById('ready-status');
      try {
        const response = await fetch('/ready');
        status.textContent = response.ok ? 'API ready' : 'API unavailable';
        status.classList.toggle('online', response.ok);
      } catch { status.textContent = 'API unavailable'; }
    };

    search.addEventListener('input', renderEndpoints);
    document.querySelectorAll('.scenario').forEach((card) => card.addEventListener('click', () => {
      search.value = '';
      renderEndpoints();
      document.getElementById('vehicles').scrollIntoView({ behavior: 'smooth' });
      setTimeout(() => {
        const endpoint = document.querySelector('[data-path="/v1/vehicles/{vin}"]');
        endpoint?.setAttribute('open', '');
        const input = endpoint?.querySelector('[data-param="vin"]');
        if (input) input.value = card.dataset.vin;
        endpoint?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 250);
    }));
    loadContract();
    checkReady();
  </script>
</body>
</html>"""
