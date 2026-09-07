import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const ossUploadProxyTarget = env.VITE_DEV_OSS_UPLOAD_PROXY_TARGET?.trim();

  return {
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      port: 5173,
      proxy: ossUploadProxyTarget
        ? {
            "/__ms_image_oss_upload": {
              target: ossUploadProxyTarget,
              changeOrigin: true,
              secure: true,
              rewrite: (path) => path.replace(/^\/__ms_image_oss_upload/, ""),
              configure: (proxy) => {
                proxy.on("proxyReq", (proxyRequest) => {
                  proxyRequest.removeHeader("origin");
                  proxyRequest.removeHeader("referer");
                });
              },
            },
          }
        : undefined,
    },
    preview: {
      host: "127.0.0.1",
      port: 4173,
    },
  };
});
