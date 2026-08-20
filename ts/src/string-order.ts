/** Stable comparison helpers for contract descriptors and canonical JSON keys. */

export function compareLocaleStrings(left: string, right: string): number {
  return left.localeCompare(right);
}

export function compareUnicodeCodePoints(left: string, right: string): number {
  const leftPoints = Array.from(left, character => character.codePointAt(0) as number);
  const rightPoints = Array.from(right, character => character.codePointAt(0) as number);
  const sharedLength = Math.min(leftPoints.length, rightPoints.length);
  for (let index = 0; index < sharedLength; index += 1) {
    if (leftPoints[index] !== rightPoints[index]) {
      return leftPoints[index] - rightPoints[index];
    }
  }
  return leftPoints.length - rightPoints.length;
}
