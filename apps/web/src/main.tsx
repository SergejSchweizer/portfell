import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./app";
import "../styles/app.css";

const rootElement = document.querySelector("#root");

if (!rootElement) {
  throw new Error("root element missing");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
