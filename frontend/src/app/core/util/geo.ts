const EARTH_RADIUS_M = 6_371_000;

/** Distancia en metros entre dos coordenadas (Haversine); misma fórmula que el servidor. */
export function haversineM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const rad = (d: number) => (d * Math.PI) / 180;
  const dPhi = rad(lat2 - lat1);
  const dLambda = rad(lon2 - lon1);
  const a =
    Math.sin(dPhi / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLambda / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(a));
}
