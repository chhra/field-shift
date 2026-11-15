"use client";

import dynamic from "next/dynamic";
import type { MapProps } from "./LeafletMap";
import styles from "./MapView.module.css";

const LeafletMap = dynamic(() => import("./LeafletMap"), {
  ssr: false,
  loading: () => <div className={styles.placeholder} aria-hidden="true" />,
});

export function MapView(props: MapProps & { className?: string }) {
  const { className, ...rest } = props;
  return (
    <div className={`${styles.frame} ${className ?? ""}`} style={{ height: props.height }}>
      <LeafletMap {...rest} />
    </div>
  );
}
