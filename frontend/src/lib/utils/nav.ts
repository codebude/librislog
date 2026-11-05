/** Whether a nav href is the current page or a nested route below it. */
export function isActivePath(pathname: string, href: string): boolean {
	return pathname === href || pathname.startsWith(`${href}/`);
}
