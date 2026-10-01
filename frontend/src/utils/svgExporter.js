/**
 * VERIDEX-AI Frontend SVG Export Utility
 * Purely presentation-layer utility for downloading rendered inline SVG charts as .svg vector files.
 * Does NOT invoke backend analytics or calculate new business data.
 */

export function exportSvgElement(svgRef, filename = 'chart.svg') {
  if (!svgRef || !svgRef.current) {
    console.warn('SVG element reference not found for export.');
    return false;
  }

  try {
    const svgEl = svgRef.current;
    const serializer = new XMLSerializer();
    let source = serializer.serializeToString(svgEl);

    // Ensure XML namespace attributes are present
    if (!source.match(/^<svg[^>]+xmlns="http:\/\/www\.w3\.org\/2000\/svg"/)) {
      source = source.replace(/^<svg/, '<svg xmlns="http://www.w3.org/2000/svg"');
    }
    if (!source.match(/^<svg[^>]+"http:\/\/www\.w3\.org\/1999\/xlink"/)) {
      source = source.replace(/^<svg/, '<svg xmlns:xlink="http://www.w3.org/1999/xlink"');
    }

    // Add XML declaration
    source = '<?xml version="1.0" standalone="no"?>\r\n' + source;

    const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(source);
    const downloadLink = document.createElement('a');
    downloadLink.href = url;
    downloadLink.download = filename;
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
    return true;
  } catch (err) {
    console.error('Failed to export SVG image:', err);
    return false;
  }
}
