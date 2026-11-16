import { useEffect, useRef } from "react";
import JsBarcode from "jsbarcode";

export default function Code128Barcode({
  value,
  className = "",
  width = 1.5,
  height = 48,
}: {
  value: string;
  className?: string;
  width?: number;
  height?: number;
}) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || !value) return;
    JsBarcode(svgRef.current, value, {
      format: "CODE128",
      displayValue: false,
      lineColor: "#111827",
      width,
      height,
      margin: 8,
    });
  }, [value, width, height]);

  return <svg ref={svgRef} role="img" aria-label={`Code 128 barcode for ${value}`} className={`h-auto max-w-full ${className}`} />;
}
