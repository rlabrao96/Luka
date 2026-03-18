"use client";
import dynamic from "next/dynamic";

// dynamic(ssr:false) must live inside a Client Component
export const ImportStatusBannerClient = dynamic(
  () =>
    import("./ImportStatusBanner").then((m) => m.ImportStatusBanner),
  { ssr: false }
);
