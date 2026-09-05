'use client';

import { useEffect, useState, useRef, useImperativeHandle, forwardRef } from 'react';
import dynamic from 'next/dynamic';

const ReactPDF = dynamic(() => import('react-pdf').then(mod => mod.Document), { ssr: false });
const ReactPDFPage = dynamic(() => import('react-pdf').then(mod => mod.Page), { ssr: false });
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

export interface PdfViewerHandle {
  jumpToPage: (page: number) => void;
}

interface PdfViewerProps {
  url: string;
  currentPage: number;
  onPageChange: (page: number) => void;
  zoom?: number;
  onZoomChange?: (zoom: number) => void;
  className?: string;
}

export const PdfViewer = forwardRef<PdfViewerHandle, PdfViewerProps>(
  function PdfViewer({ url, currentPage, onPageChange, zoom = 1, onZoomChange, className }, ref) {
    const [numPages, setNumPages] = useState(0);
    const [containerWidth, setContainerWidth] = useState(600);
    const containerRef = useRef<HTMLDivElement>(null);
    const suppressScrollRef = useRef(false);

    useEffect(() => {
      import('react-pdf').then(({ pdfjs }) => {
        pdfjs.GlobalWorkerOptions.workerSrc =
          `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
      });
    }, []);

    useEffect(() => {
      const updateWidth = () => {
        const parent = containerRef.current?.parentElement;
        if (parent) {
          setContainerWidth(parent.clientWidth - 48);
        }
      };
      updateWidth();
      window.addEventListener('resize', updateWidth);
      return () => window.removeEventListener('resize', updateWidth);
    }, []);

    useImperativeHandle(ref, () => ({
      jumpToPage: (page: number) => {
        suppressScrollRef.current = true;
        onPageChange(page);
        setTimeout(() => { suppressScrollRef.current = false; }, 500);
      },
    }));

    const handleScroll = () => {
      if (suppressScrollRef.current || numPages <= 1) return;
      const container = containerRef.current;
      if (!container) return;

      const pages = container.querySelectorAll('[data-page-number]');
      let closest = 1;
      let minDist = Infinity;
      const containerRect = container.getBoundingClientRect();

      pages.forEach((el) => {
        const page = parseInt(el.getAttribute('data-page-number') || '1', 10);
        const rect = el.getBoundingClientRect();
        const dist = Math.abs(rect.top - containerRect.top);
        if (dist < minDist) {
          minDist = dist;
          closest = page;
        }
      });

      if (closest !== currentPage) {
        onPageChange(closest);
      }
    };

    const pageWidth = Math.max(300, containerWidth * zoom);

    return (
      <div className={className}>
        <div className="pdf-toolbar">
          <div className="pdf-nav">
            <button
              onClick={() => onPageChange(Math.max(1, currentPage - 1))}
              disabled={currentPage <= 1}
              className="btn btn-ghost btn-sm"
              style={{ opacity: currentPage <= 1 ? 0.4 : 1 }}
            >
              Prev
            </button>
            <span className="pdf-page-info">
              {currentPage} / {numPages}
            </span>
            <button
              onClick={() => onPageChange(Math.min(numPages, currentPage + 1))}
              disabled={currentPage >= numPages}
              className="btn btn-ghost btn-sm"
              style={{ opacity: currentPage >= numPages ? 0.4 : 1 }}
            >
              Next
            </button>
          </div>
          <div className="pdf-zoom">
            <button
              onClick={() => onZoomChange?.(Math.max(0.5, zoom - 0.1))}
              className="btn btn-ghost btn-sm"
            >
              −
            </button>
            <span className="pdf-zoom-label">{Math.round(zoom * 100)}%</span>
            <button
              onClick={() => onZoomChange?.(Math.min(2, zoom + 0.1))}
              className="btn btn-ghost btn-sm"
            >
              +
            </button>
          </div>
        </div>
        <div
          ref={containerRef}
          className="pdf-container"
          onScroll={handleScroll}
        >
          <ReactPDF
            file={url}
            onLoadSuccess={({ numPages: n }) => setNumPages(n)}
            loading={<div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--ink-50)' }}>Loading PDF...</div>}
            error={<div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--flag)' }}>Failed to load PDF</div>}
          >
            <ReactPDFPage pageNumber={currentPage} width={pageWidth} />
          </ReactPDF>
        </div>
      </div>
    );
  }
);
