import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { XrayWorkspacePage } from "./pages/XrayWorkspacePage";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <XrayWorkspacePage />
  </StrictMode>,
);
