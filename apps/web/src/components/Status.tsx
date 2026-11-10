import type { ReactNode } from "react";

type Props = { kind: "loading" | "error" | "empty" | "info"; children: ReactNode };

/** Uniform loading / error / empty / partial-data message, announced to screen readers. */
export function Status({ kind, children }: Props) {
  return (
    <p className={`status status--${kind}`} role={kind === "error" ? "alert" : "status"}>
      {children}
    </p>
  );
}
