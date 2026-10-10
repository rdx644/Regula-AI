"use client";

import { createContext, useContext } from "react";

export type Capabilities = {
  model_execution_enabled: boolean;
  synthetic_extraction_enabled: boolean;
  max_upload_bytes: number;
  ephemeral_uploads: boolean;
};

export const CapabilitiesContext = createContext<Capabilities | null>(null);
export const useCapabilities = () => useContext(CapabilitiesContext);
