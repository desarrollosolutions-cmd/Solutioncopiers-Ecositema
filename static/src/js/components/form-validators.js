/**
 * Validadores client-side reutilizables.
 */

export function validateRequired(value) {
  return value !== null && value !== undefined && String(value).trim() !== "";
}

export function validateEmail(email) {
  if (!email) return false;
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
}

export function validateColombianPhone(phone) {
  if (!phone) return false;
  const cleaned = phone.replace(/[^\d+]/g, "");
  const re = /^(\+57)?[3]\d{9}$|^\+57[1-8]\d{7,9}$/;
  return re.test(cleaned);
}

export function validateNumber(value, min, max) {
  const num = Number(value);
  if (isNaN(num)) return false;
  if (min !== undefined && num < min) return false;
  if (max !== undefined && num > max) return false;
  return true;
}

export function validateMinLength(value, minLength) {
  if (!value) return false;
  return String(value).trim().length >= minLength;
}
