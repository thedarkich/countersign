import type { Attempt } from '../api/types'
import { useLang } from '../i18n'

const W = 595
const H = 842
const CJK = '"PingFang SC","Noto Sans SC","Microsoft YaHei",sans-serif'

/**
 * Shows what the AI read. With a backend preview image, hidden-text boxes are drawn over it
 * (PyMuPDF bboxes use a top-left origin in PDF points). Without one, a 发票-style sheet is
 * drawn from the extracted fields so mock attempts and text inputs still have something to show.
 */
export function InvoicePreview({ attempt, showHidden }: { attempt: Attempt; showHidden: boolean }) {
  const { tr } = useLang()
  const hidden = attempt.hidden_text
  const [pw, ph] = hidden?.page_size ?? [W, H]

  const overlays =
    showHidden && hidden?.spans.length
      ? hidden.spans.map((s, i) => (
          <div
            key={i}
            className="absolute border border-cinnabar"
            style={{
              left: `${(s.bbox[0] / pw) * 100}%`,
              top: `${(s.bbox[1] / ph) * 100}%`,
              width: `${Math.max(1, ((s.bbox[2] - s.bbox[0]) / pw) * 100)}%`,
              height: `${Math.max(0.8, ((s.bbox[3] - s.bbox[1]) / ph) * 100)}%`,
              background: 'rgba(207,42,31,0.14)',
            }}
            title={s.text}
          />
        ))
      : null

  if (attempt.preview_url) {
    return (
      <div className="relative ruled overflow-hidden bg-white">
        <img src={attempt.preview_url} alt={tr('Invoice preview', '发票预览')} className="block w-full" />
        {overlays}
      </div>
    )
  }

  const x = attempt.extraction
  if (!x || !x.is_invoice) {
    return (
      <div className="ruled bg-field p-4 font-mono text-sm leading-relaxed text-ink2">
        <p className="mb-2 font-sans text-xs">{tr('Message as received', '收到的原文')}</p>
        {x?.visible_text || attempt.file_name || tr('(empty)', '（空）')}
      </div>
    )
  }

  const payoutFlag = attempt.flags.some((f) => f.code === 'PAYOUT_CHANGED')
  const amount = x.amount_total != null ? x.amount_total.toFixed(2) : '—'
  const line = (y: number) => <line x1="40" y1={y} x2={W - 40} y2={y} stroke="#9a5246" strokeWidth="1" />
  const cell = (label: string, value: string, y: number, danger = false, mono = false) => (
    <g>
      <text x="52" y={y} fontSize="12" fill="#8e4a3f" style={{ fontFamily: CJK }}>
        {label}
      </text>
      <text x="170" y={y} fontSize={mono ? 12 : 14} fill={danger ? '#cf2a1f' : '#1d2836'} fontWeight={danger ? 700 : 500} style={{ fontFamily: mono ? '"IBM Plex Mono",monospace' : CJK }}>
        {value}
      </text>
    </g>
  )

  return (
    <div className="ruled overflow-hidden bg-white">
      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="img" aria-label={tr('Invoice as read by the AI', 'AI 读到的发票')}>
        <rect x="24" y="24" width={W - 48} height={H - 48} fill="#fcfdfb" stroke="#9a5246" strokeWidth="2" />
        <rect x="30" y="30" width={W - 60} height={H - 60} fill="none" stroke="#9a5246" strokeWidth="0.8" />
        <text x={W / 2} y="92" textAnchor="middle" fontSize="34" fontWeight="800" fill="#8e4a3f" letterSpacing="14" style={{ fontFamily: CJK }}>
          发 票
        </text>
        <text x={W / 2} y="114" textAnchor="middle" fontSize="12" fill="#8e4a3f" letterSpacing="6" style={{ fontFamily: '"Archivo Variable",sans-serif' }}>
          INVOICE
        </text>
        <line x1={W / 2 - 80} y1="124" x2={W / 2 + 80} y2="124" stroke="#8e4a3f" strokeWidth="1.4" />
        <line x1={W / 2 - 80} y1="128" x2={W / 2 + 80} y2="128" stroke="#8e4a3f" strokeWidth="0.8" />

        <text x={W - 52} y="80" textAnchor="end" fontSize="11" fill="#8e4a3f" style={{ fontFamily: CJK }}>
          发票号码 No.
        </text>
        <text x={W - 52} y="98" textAnchor="end" fontSize="14" fill="#cf2a1f" style={{ fontFamily: '"IBM Plex Mono",monospace' }}>
          {x.invoice_number ?? '—'}
        </text>
        <text x={W - 52} y="122" textAnchor="end" fontSize="11" fill="#1d2836" style={{ fontFamily: CJK }}>
          开票日期 {x.invoice_date ?? '—'}
        </text>

        {line(160)}
        {cell('销售方 Vendor', x.vendor_name ?? '—', 188)}
        {line(204)}
        {cell('采购单 PO', x.po_reference ?? '—', 232)}
        {line(248)}
        {cell('收款地址 Pay to', x.payee_address ?? tr('(not printed)', '（未注明）'), 276, payoutFlag, true)}
        {line(292)}
        <line x1="160" y1="160" x2="160" y2="292" stroke="#9a5246" strokeWidth="1" />

        <rect x="40" y="320" width={W - 80} height="30" fill="#f3e9e6" />
        <text x="52" y="340" fontSize="12" fill="#8e4a3f" style={{ fontFamily: CJK }}>
          项目 Item
        </text>
        <text x={W - 52} y="340" textAnchor="end" fontSize="12" fill="#8e4a3f" style={{ fontFamily: CJK }}>
          金额 Amount
        </text>
        <text x="52" y="378" fontSize="14" fill="#1d2836" style={{ fontFamily: CJK }}>
          {tr('Services', '服务费')}
        </text>
        <text x={W - 52} y="378" textAnchor="end" fontSize="14" fill="#1d2836" style={{ fontFamily: '"IBM Plex Mono",monospace' }}>
          {amount}
        </text>
        {line(400)}
        <text x="52" y="430" fontSize="13" fontWeight="700" fill="#8e4a3f" style={{ fontFamily: CJK }}>
          价税合计 Total
        </text>
        <text x={W - 52} y="432" textAnchor="end" fontSize="20" fontWeight="700" fill="#1d2836" style={{ fontFamily: '"IBM Plex Mono",monospace' }}>
          {amount} {x.currency ?? ''}
        </text>
        {line(452)}

        <text x="52" y="490" fontSize="12" fill="#8e4a3f" style={{ fontFamily: CJK }}>
          备注 Notes
        </text>
        <foreignObject x="52" y="500" width={W - 104} height="120">
          <div style={{ fontFamily: CJK, fontSize: 13, color: '#1d2836', lineHeight: 1.5 }}>{x.notes_to_payer ?? ''}</div>
        </foreignObject>

        {/* the hidden text, nearly invisible on paper, exactly as an attacker would plant it */}
        {hidden?.spans.map((s, i) => (
          <g key={i}>
            {showHidden && (
              <rect x={s.bbox[0] - 3} y={s.bbox[1] - 3} width={s.bbox[2] - s.bbox[0] + 6} height={Math.max(8, s.bbox[3] - s.bbox[1] + 6)} fill="rgba(207,42,31,0.14)" stroke="#cf2a1f" strokeWidth="1" />
            )}
            <text
              x={s.bbox[0]}
              y={s.bbox[3] - 1}
              fontSize={s.reason === 'tiny_font' ? 3 : Math.max(6, Math.min(11, s.bbox[3] - s.bbox[1]))}
              textLength={Math.max(4, s.bbox[2] - s.bbox[0])}
              lengthAdjust="spacingAndGlyphs"
              fill={showHidden ? '#cf2a1f' : '#f4f6f2'}
              style={{ fontFamily: CJK }}
            >
              {s.text}
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}
