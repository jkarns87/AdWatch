import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  images: { remotePatterns: [{ protocol: "https", hostname: "**" }] },
  // Alerts already delivered to Slack/Teams carry /w/{id} links; renaming the
  // route doesn't rewrite sent messages. Keep this permanently.
  async redirects() {
    return [{ source: "/w/:id", destination: "/watchlists/:id", permanent: true }];
  },
};

export default nextConfig;
