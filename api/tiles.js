// Edge function: proxy for CARTO dark basemap tiles.
// The basemaps key stays in the CARTO_BASEMAPS_KEY environment variable
// and never reaches the browser. URL: /api/tiles?z={z}&x={x}&y={y}&r={r}
// (r = "@2x" on retina displays, empty otherwise).
export const config = { runtime: 'edge' };

const STYLE = 'dark_all';
const MAX_ZOOM = 20;

export default async function handler(request) {
  const url = new URL(request.url);
  const z = Number.parseInt(url.searchParams.get('z'), 10);
  const x = Number.parseInt(url.searchParams.get('x'), 10);
  const y = Number.parseInt(url.searchParams.get('y'), 10);
  const retina = url.searchParams.get('r') === '@2x' ? '@2x' : '';

  // Only well-formed tile coordinates are proxied: the upstream URL is
  // built from validated integers and a fixed style, nothing user-supplied.
  const n = 2 ** z;
  if (![z, x, y].every(Number.isInteger) || z < 0 || z > MAX_ZOOM ||
      x < 0 || y < 0 || x >= n || y >= n) {
    return new Response('bad tile coordinates', { status: 400 });
  }

  const key = process.env.CARTO_BASEMAPS_KEY;
  if (!key) {
    return new Response('CARTO_BASEMAPS_KEY environment variable is not set', { status: 500 });
  }

  const upstream = 'https://a.basemaps.cartocdn.com/' + STYLE +
    '/' + z + '/' + x + '/' + y + retina + '.png?key=' + encodeURIComponent(key);

  const resp = await fetch(upstream);
  if (!resp.ok) {
    return new Response('upstream error', { status: resp.status === 404 ? 404 : 502 });
  }

  const headers = new Headers();
  headers.set('Content-Type', resp.headers.get('Content-Type') || 'image/png');
  headers.set('Cache-Control', 'public, max-age=2592000, s-maxage=2592000, immutable');
  return new Response(resp.body, { status: 200, headers });
}
