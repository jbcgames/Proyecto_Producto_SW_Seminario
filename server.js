// Requiere Node 18+ (usa fetch nativo)
import express from "express";
import crypto from "crypto";
import cookieParser from "cookie-parser";

const app = express();
app.use(cookieParser());

/** ====== CONFIG ====== **/
const APP_ID = process.env.MELI_APP_ID || "4879301027101480";
const CLIENT_SECRET = process.env.MELI_CLIENT_SECRET || "2vYX1YzwmlpSyHusAl15zLGUH0cDc2JE";
const REDIRECT_URI = process.env.MELI_REDIRECT_URI || "http://localhost:3000/callback";
// Usa el auth del país (para Colombia):
const AUTH_BASE = process.env.MELI_AUTH_BASE || "https://auth.mercadolibre.com.co";
const TOKEN_URL  = "https://api.mercadolibre.com/oauth/token";
const SITE_ID = "MCO"; // Colombia

/** ====== ALMACENAMIENTO SIMPLE (DEMO) ====== **/
// Guardamos en memoria el code_verifier por estado y el access_token
const pkceStore = new Map();   // state -> code_verifier
let ACCESS_TOKEN = null;

/** ====== UTILIDADES PKCE ====== **/
function base64url(buffer) {
  return Buffer.from(buffer)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function generateCodeVerifier(len = 64) {
  return base64url(crypto.randomBytes(len));
}

function generateCodeChallengeS256(codeVerifier) {
  const hash = crypto.createHash("sha256").update(codeVerifier).digest();
  return base64url(hash);
}

function randomState() {
  return base64url(crypto.randomBytes(24));
}

/** ====== RUTAS ====== **/

// 1) Iniciar login con PKCE
app.get("/login", (req, res) => {
  const state = randomState();
  const codeVerifier = generateCodeVerifier();
  const codeChallenge = generateCodeChallengeS256(codeVerifier);

  // Guardamos el code_verifier asociado al state
  pkceStore.set(state, codeVerifier);

  const url = new URL(`${AUTH_BASE}/authorization`);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("client_id", APP_ID);
  url.searchParams.set("redirect_uri", REDIRECT_URI);
  url.searchParams.set("code_challenge", codeChallenge);
  url.searchParams.set("code_challenge_method", "S256");
  url.searchParams.set("state", state);

  res.redirect(url.toString());
});

// 2) Callback: intercambiar code -> token
app.get("/callback", async (req, res) => {
  try {
    const { code, state, error, error_description } = req.query;
    if (error) {
      return res.status(400).send(`Error OAuth: ${error} - ${error_description || ""}`);
    }
    if (!code || !state) {
      return res.status(400).send("Faltan parámetros 'code' o 'state'.");
    }

    const codeVerifier = pkceStore.get(state);
    if (!codeVerifier) {
      return res.status(400).send("State inválido o expirado.");
    }
    // Consumimos el state
    pkceStore.delete(state);

    const body = new URLSearchParams({
      grant_type: "authorization_code",
      client_id: APP_ID,
      client_secret: CLIENT_SECRET,     // En PKCE, ML pide también client_secret
      code,
      redirect_uri: REDIRECT_URI,
      code_verifier: codeVerifier,
    });

    const tokenRes = await fetch(TOKEN_URL, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });

    const tokenJson = await tokenRes.json();
    if (!tokenRes.ok) {
      return res
        .status(tokenRes.status)
        .send(`Fallo al obtener token: ${tokenRes.status} ${JSON.stringify(tokenJson)}`);
    }

    ACCESS_TOKEN = tokenJson.access_token; // Guardamos para esta demo
    // Opcional: guarda refresh_token para renovar
    // const REFRESH_TOKEN = tokenJson.refresh_token;

    res.send(`
      <h2>¡Autorización OK!</h2>
      <p>access_token guardado en memoria para esta sesión de demo.</p>
      <p>Prueba <a href="/buscar?q=raspberry%20pi">/buscar?q=raspberry%20pi</a></p>
    `);
  } catch (e) {
    res.status(500).send(`Error en /callback: ${e.message}`);
  }
});

// 3) Buscar artículos
// Ej: GET /buscar?q=raspberry pi&max=500000
app.get("/buscar", async (req, res) => {
  try {
    if (!ACCESS_TOKEN) {
      return res.status(401).send("No hay access_token. Primero ve a /login y autoriza.");
    }
    const q = (req.query.q || "").toString();
    const max = req.query.max ? Number(req.query.max) : undefined;
    if (!q) return res.status(400).send("Falta parámetro q.");

    const url = new URL(`https://api.mercadolibre.com/sites/${SITE_ID}/search`);
    url.searchParams.set("q", q);
    url.searchParams.set("sort", "price_asc");
    url.searchParams.set("limit", "20");

    const r = await fetch(url, {
      headers: { Authorization: `Bearer ${ACCESS_TOKEN}` },
    });
    const json = await r.json();
    if (!r.ok) {
      return res.status(r.status).send(`Error búsqueda: ${r.status} ${JSON.stringify(json)}`);
    }

    let items = (json.results || []).map(it => ({
      id: it.id,
      title: it.title,
      price: it.price,
      permalink: it.permalink,
      thumbnail: it.thumbnail,
    }));

    if (Number.isFinite(max)) {
      items = items.filter(it => it.price <= max);
    }

    res.json({ count: items.length, items });
  } catch (e) {
    res.status(500).send(`Error en /buscar: ${e.message}`);
  }
});

app.get("/", (_req, res) => {
  res.send(`
    <h1>Demo ML OAuth + Búsqueda</h1>
    <ul>
      <li><a href="/login">/login</a> (inicia autorización)</li>
      <li><a href="/buscar?q=raspberry%20pi">/buscar?q=raspberry%20pi</a> (requiere token)</li>
    </ul>
  `);
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Servidor en http://localhost:${PORT}`);
  console.log(`1) Ir a http://localhost:${PORT}/login`);
});
