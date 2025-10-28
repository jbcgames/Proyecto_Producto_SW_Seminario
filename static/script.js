const form = document.getElementById('searchForm');
const resultsDiv = document.getElementById('results');
const metaDiv = document.getElementById('meta');

let timer = null;
let sessionId = null; // para separar streams de "nuevos" por sesión

function renderItems(items) {
  if (!items || items.length === 0) return "";

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

  // Nueva sesión para que el servidor lleve visto por esta búsqueda
  sessionId = Date.now().toString();

  const q = document.getElementById('q').value;
  const min_price = document.getElementById('min_price').value;
  const max_price = document.getElementById('max_price').value;
  const condition = document.getElementById('condition').value;
  const envio = document.getElementById('envio').value;
  const site = document.getElementById('site').value;
  const refresh_sec = Math.max(10, parseInt(document.getElementById('refresh_sec').value || "60", 10));
  // const telefono = document.getElementById('telefono').value; // (guardado futuro)

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

  // 1) Primera llamada: traer "nuevos" respecto a servidor (vacío → todo es nuevo)
  try {
    const data = await fetchDelta(baseParams);
    const html = renderItems(data.new_results || []);
    resultsDiv.insertAdjacentHTML('afterbegin', html);
    metaDiv.textContent = `🔁 Auto-refresh cada ${refresh_sec}s | nuevos: ${data.new_count || 0} | total vistos servidor: ${data.total_seen || 0}`;
  } catch (err) {
    console.error(err);
    metaDiv.textContent = `❌ Error inicial: ${err.message}`;
    return;
  }

  // 2) Intervalo: preguntar SOLO nuevos
  timer = setInterval(async () => {
    try {
      const data = await fetchDelta(baseParams);
      if (data.new_results && data.new_results.length > 0) {
        const html = renderItems(data.new_results);
        // Insertar arriba (nuevos primero)
        resultsDiv.insertAdjacentHTML('afterbegin', html);
      }
      metaDiv.textContent = `🔁 Auto-refresh cada ${refresh_sec}s | nuevos: ${data.new_count || 0} | total vistos servidor: ${data.total_seen || 0}`;
    } catch (err) {
      console.error(err);
      metaDiv.textContent = `❌ Error en refresh: ${err.message}`;
    }
  }, refresh_sec * 1000);
});
