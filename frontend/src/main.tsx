import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./styles/theme.css";
import "./styles/global.css";
import "./styles/home.css";
import "./styles/rotation.css";
import "./styles/planner.css";

const client = new QueryClient({
  defaultOptions: { queries: { refetchInterval: 5000, staleTime: 2000 } },
});

// installable app (PWA): register the service worker once the page has loaded
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  });
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
