/** @type {import('next').NextConfig} */
module.exports = {
  reactStrictMode: true,
  // Only for `next dev`: lets Codespaces' forwarded address use the dev server.
  allowedDevOrigins: ["*.app.github.dev"],
  // The public site uses Unsplash photos as placeholders until the real ones arrive.
  images: {
    remotePatterns: [{ protocol: "https", hostname: "images.unsplash.com" }],
  },
};
