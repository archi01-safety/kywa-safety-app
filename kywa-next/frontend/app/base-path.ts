// Next.js embeds this value at build time. APP_BASE_PATH must match the server.
export const basePath = process.env.NEXT_PUBLIC_APP_BASE_PATH || "";
export const authChannel = `kywa-auth${basePath}`;

export function appPath(path: string): string {
  if (!path.startsWith("/") || path.startsWith("//")) return path;
  if (basePath && (path === basePath || path.startsWith(basePath + "/"))) return path;
  return basePath + path;
}
