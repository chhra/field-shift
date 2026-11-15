"use client";

import dynamic from "next/dynamic";
import type { MapProps } from "./LeafletMap";
import styles from "./MapView.module.css";

const LeafletMap = dynamic(() => import("./LeafletMap"), {
  ssr: false,
  loading: () => <div className={styles.placeholder} aria-hidden="true" />,
});

export function MapView(props: MapProps & { className?: string; flush?: boolean }) {
  const { className, flush, ...rest } = props;
  const cls = [styles.frame, flush ? styles.flush : "", className ?? ""].join(" ");
  return (
    <div className={cls} style={{ height: props.height }}>
      <LeafletMap {...rest} />
    </div>
  );
}
