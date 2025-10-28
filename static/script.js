const form = document.getElementById('searchForm');
const resultsDiv = document.getElementById('results');
const metaDiv = document.getElementById('meta');

let timer = null;
let sessionId = null;

function renderItems(items) {
  if (!items || items.length === 0) return "<p>Sin nuevos resultados en este ciclo.</p>";

  return items.map(item => {
    const condition = item.condition && item.condition.toLowerCase() === 'usado' ? 'Usado' : 'Nuevo';
    const shipping = item.shipping || 'No especificado';
    const image = item.image || 'https://via.placeholder.com/120x120?text=Sin+Imagen';
    const priceFmt = (item.price || 0).toLocaleString('es-CO');

    return `
      <div class="result-card">
        <img src="${image}" alt="img" />
        <div class="info-box">
          <a href="${item.link}" target="_blank">${item.title}</a><br/>
          💰 ${priceFmt} COP<br/>
          🏷️ ${condition} | 🚚 ${shipping}
        </div>
      </div>
    `;
  }).join('');
}

async function fetchDelta(params) {
  const url = `/search?${params.toString()}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (timer) { clearInterval(timer); timer = null; }
  resultsDiv.innerHTML = "";
  metaDiv.textContent = "🔄 Buscando…";

  sessionId = Date.now().toString();

  const q = document.getElementById('q').value;
  const min_price = document.getElementById('min_price').value;
  const max_price = document.getElementById('max_price').value;
  const condition = document.getElementById('condition').value;
  const envio = document.getElementById('envio').value;
  const site = document.getElementById('site').value;
  const refresh_sec = Math.max(10, parseInt(document.getElementById('refresh_sec').value || "60", 10));
const btnSubscribe = document.getElementById('btnSubscribe');

btnSubscribe.addEventListener('click', async () => {
  const q = document.getElementById('q').value.trim();
  const min_price = document.getElementById('min_price').value;
  const max_price = document.getElementById('max_price').value;
  const condition = document.getElementById('condition').value;
  const envio = document.getElementById('envio').value;
  const site = document.getElementById('site').value;
  const refresh_sec = Math.max(30, parseInt(document.getElementById('refresh_sec').value || "300", 10));
  const phone = document.getElementById('telefono').value.trim();

  if (!q || !phone) {
    alert("Completa la palabra clave y el teléfono.");
    return;
  }

  // (opcional) registrar chat si ya tienes el chat_id (manual temporal)
  // await fetch('/register_chat', {method:'POST', headers:{'Content-Type':'application/json'},
  //   body: JSON.stringify({ phone, chat_id: 'TU_CHAT_ID' })});

  try {
    const res = await fetch('/subscribe', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        q, phone,
        min_price: min_price ? parseInt(min_price,10) : null,
        max_price: max_price ? parseInt(max_price,10) : null,
        condition: condition || null,
        envio: envio || null,
        site,
        interval_sec: refresh_sec
      })
    });
    const data = await res.json();
    if (data.ok) {
      alert("✅ Suscripción creada. El bot te enviará SOLO los nuevos.");
    } else {
      alert("❌ Error creando suscripción.");
    }
  } catch (e) {
    alert("❌ Error de red en suscripción");
  }
});

  const baseParams = new URLSearchParams({
    q,
    site,
    delta: "true",
    session_id: sessionId,
    ...(min_price && { min_price }),
    ...(max_price && { max_price }),
    ...(condition && { condition }),
    ...(envio && { envio }),
  });

  // 1) Primer ciclo: pinta SOLO los nuevos (que serán todos la primera vez)
  try {
    const data = await fetchDelta(baseParams);
    resultsDiv.innerHTML = renderItems(data.new_results || []);
    metaDiv.textContent = `🔁 Auto-refresh ${refresh_sec}s | nuevos: ${data.new_count || 0} | total vistos servidor: ${data.total_seen || 0}`;
  } catch (err) {
    console.error(err);
    metaDiv.textContent = `❌ Error inicial: ${err.message}`;
    return;
  }

  // 2) Siguientes ciclos: reemplaza el contenido con el NUEVO lote
  timer = setInterval(async () => {
    try {
      const data = await fetchDelta(baseParams);
      resultsDiv.innerHTML = renderItems(data.new_results || []);
      metaDiv.textContent = `🔁 Auto-refresh ${refresh_sec}s | nuevos: ${data.new_count || 0} | total vistos servidor: ${data.total_seen || 0}`;
    } catch (err) {
      console.error(err);
      metaDiv.textContent = `❌ Error en refresh: ${err.message}`;
    }
  }, refresh_sec * 1000);
});
