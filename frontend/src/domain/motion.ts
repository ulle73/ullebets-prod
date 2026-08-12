export function signalCardHover(reducedMotion: boolean): { y?: number } {
  return reducedMotion ? {} : { y: -2 };
}
