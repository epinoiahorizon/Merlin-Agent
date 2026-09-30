export function isOnboardingEnabled(): boolean {
  return window.merlinDesktop?.guestOnboardingEnabled === true
}
