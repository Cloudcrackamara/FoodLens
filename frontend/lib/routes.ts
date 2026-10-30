/**
 * Consumer check screens (/check and /p/{token}) draw their own demo banner and consumer header,
 * as in the design boards, so the site-wide banner and header are left off there.
 */
export function isConsumerCheckPath(pathname: string | null): boolean {
  if (!pathname) return false;
  return pathname === "/check" || pathname.startsWith("/check/") || pathname.startsWith("/p/");
}

/** The merchant pages draw their own banner and workspace shell (design/README.md, component 5). */
export function isMerchantPath(pathname: string | null): boolean {
  return pathname === "/merchant" || (pathname?.startsWith("/merchant/") ?? false);
}
