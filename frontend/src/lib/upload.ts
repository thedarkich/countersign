// Phone photos are often 4–12 MB. The backend takes 5 MB at most, so big images are
// shrunk in the browser first. 2400 px on the long edge keeps small invoice print readable.
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024
const SHRINK_ABOVE = 1.5 * 1024 * 1024
const LONG_EDGE = 2400

export class UploadError extends Error {
  constructor(public code: 'too_big' | 'wrong_type') {
    super(code)
  }
}

const isPdf = (f: File) => f.type === 'application/pdf' || /\.pdf$/i.test(f.name)
const isImage = (f: File) => /^image\//.test(f.type) || /\.(jpe?g|png|webp|heic|heif)$/i.test(f.name)

function decode(file: File): Promise<{ img: CanvasImageSource; w: number; h: number; done: () => void }> {
  if (typeof createImageBitmap === 'function') {
    return createImageBitmap(file).then((b) => ({ img: b, w: b.width, h: b.height, done: () => b.close() }))
  }
  // older webviews: go through an <img>
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const el = new Image()
    el.onload = () => resolve({ img: el, w: el.naturalWidth, h: el.naturalHeight, done: () => URL.revokeObjectURL(url) })
    el.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('decode failed'))
    }
    el.src = url
  })
}

async function shrink(file: File): Promise<File> {
  const { img, w, h, done } = await decode(file)
  try {
    const scale = Math.min(1, LONG_EDGE / Math.max(w, h))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(w * scale)
    canvas.height = Math.round(h * scale)
    const ctx = canvas.getContext('2d')
    if (!ctx) return file
    ctx.fillStyle = '#ffffff' // transparent PNGs would turn black as JPEG
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, 'image/jpeg', 0.85))
    if (!blob || blob.size >= file.size) return file
    return new File([blob], file.name.replace(/\.[^.]+$/, '') + '.jpg', { type: 'image/jpeg' })
  } finally {
    done()
  }
}

/** Returns a file that is safe to upload, or throws UploadError. */
export async function prepareUpload(file: File): Promise<File> {
  if (isPdf(file)) {
    if (file.size > MAX_UPLOAD_BYTES) throw new UploadError('too_big')
    return file
  }
  if (!isImage(file)) throw new UploadError('wrong_type')
  if (file.size <= SHRINK_ABOVE) return file
  let out = file
  try {
    out = await shrink(file)
  } catch {
    /* this browser can't decode it (HEIC outside Safari, say); send the original if it fits */
  }
  if (out.size > MAX_UPLOAD_BYTES) throw new UploadError('too_big')
  return out
}

export const kb = (n: number) => (n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`)
