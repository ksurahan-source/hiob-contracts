/** Reject values whose canonical JSON meaning differs across Python and JS. */
export function assertStrictCanonicalValue(value: unknown, path = 'contract'): void {
  if (value === null || typeof value === 'boolean') return;
  if (typeof value === 'string') {
    for (let index = 0; index < value.length; index += 1) {
      const code = value.charCodeAt(index);
      if (code >= 0xd800 && code <= 0xdbff) {
        const next = value.charCodeAt(index + 1);
        if (!(next >= 0xdc00 && next <= 0xdfff)) {
          throw new TypeError(`${path} contains an unpaired Unicode surrogate`);
        }
        index += 1;
      } else if (code >= 0xdc00 && code <= 0xdfff) {
        throw new TypeError(`${path} contains an unpaired Unicode surrogate`);
      }
    }
    return;
  }
  if (typeof value === 'number') {
    if (!Number.isSafeInteger(value)) {
      throw new TypeError(`${path} numbers must be safe integers`);
    }
    return;
  }
  if (Array.isArray(value)) {
    for (let index = 0; index < value.length; index += 1) {
      if (!Object.prototype.hasOwnProperty.call(value, index)) {
        throw new TypeError(`${path} contains a sparse array`);
      }
      assertStrictCanonicalValue(value[index], `${path}[${index}]`);
    }
    return;
  }
  if (typeof value === 'object' && Object.getPrototypeOf(value) === Object.prototype) {
    Object.entries(value as Record<string, unknown>).forEach(([key, item]) => {
      assertStrictCanonicalValue(item, `${path}.${key}`);
    });
    return;
  }
  throw new TypeError(`${path} contains a non-JSON value`);
}

export function strictUtcMicros(value: string): number {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?Z$/.exec(value);
  if (!match) throw new TypeError('timestamp must be strict UTC');
  const [, yearText, monthText, dayText, hourText, minuteText, secondText, fraction = ''] = match;
  const parts = [yearText, monthText, dayText, hourText, minuteText, secondText].map(Number);
  const [year, month, day, hour, minute, second] = parts;
  const millis = Number(fraction.padEnd(6, '0').slice(0, 3));
  const instant = new Date(Date.UTC(year, month - 1, day, hour, minute, second, millis));
  if (
    instant.getUTCFullYear() !== year || instant.getUTCMonth() !== month - 1
    || instant.getUTCDate() !== day || instant.getUTCHours() !== hour
    || instant.getUTCMinutes() !== minute || instant.getUTCSeconds() !== second
  ) throw new TypeError('timestamp must be a real UTC calendar instant');
  return instant.getTime() * 1000 + Number(fraction.padEnd(6, '0').slice(3, 6));
}
