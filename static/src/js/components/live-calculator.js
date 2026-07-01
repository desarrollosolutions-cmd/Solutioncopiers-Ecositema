/**
 * Cliente API para el cálculo en vivo del cotizador.
 */
export async function calculateLiveEstimate(interestArea, details) {
  const csrfToken = getCSRFToken();

  const payload = {
    interest_area: interestArea,
    ...details,
  };

  try {
    const response = await fetch("/cotizador/api/calcular/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify(payload),
    });
    return await response.json();
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

function getCSRFToken() {
  const cookie = document.cookie
    .split("; ")
    .find((c) => c.startsWith("csrftoken="));
  return cookie ? cookie.split("=")[1] : "";
}
