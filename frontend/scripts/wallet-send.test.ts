// Review finding 1: a sent payment whose report fails must never lead to a second payment.
// Run: npm run test:wallet  (esbuild bundles this file, then node:test runs it)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import type { Approval, WalletPayment } from '../src/lib/walletApi'
import { payOnce, record, type ReportStore } from '../src/lib/walletSend'

const HASH = ('0x' + 'ab'.repeat(32)) as `0x${string}`

function memoryStore(): ReportStore & { raw: string } {
  const s = { raw: '[]', load: () => JSON.parse(s.raw), save: (list: unknown[]) => void (s.raw = JSON.stringify(list)) }
  return s
}

function world() {
  const sends: string[] = []
  const recorded = new Map<string, string>() // payment id -> hash, as the server keeps it
  let reportMode: 'ok' | 'unreachable' | 'lost-response' = 'ok'
  const payment = (id: string, status: WalletPayment['status']): WalletPayment => ({
    id, status, payee: '0x94Eb49F414A609c954e623fc5216a0944Aa4e0c4', payee_label: 'Owner', amount: '0.01',
    tx_hash: recorded.get(id) ?? null, explorer_url: null, block_number: null, detail: null, created_at: '',
  })
  const approve = async (): Promise<Approval> => ({
    payment: payment('p1', 'approved'),
    tx: { from: '0xCEC6a9DFA4318A9AacFF50a8fdC88eBb20059272', to: '0x94Eb49F414A609c954e623fc5216a0944Aa4e0c4', value: '10000000000000000', chain_id: 677 },
  })
  const send = async () => (sends.push(HASH), HASH)
  const sent = async (id: string, hash: string) => {
    if (reportMode === 'unreachable') throw new TypeError('Failed to fetch')
    const known = recorded.get(id)
    if (known && known !== hash) throw new Error('409 different hash')
    recorded.set(id, hash) // idempotent: the same hash again is fine
    if (reportMode === 'lost-response') throw new TypeError('Failed to fetch')
    return { payment: payment(id, 'sent') }
  }
  return { sends, recorded, approve, send, sent, setReport: (m: typeof reportMode) => void (reportMode = m) }
}

test('the report never reaches the server: one send, then a retry only reports', async () => {
  const w = world()
  const store = memoryStore()
  w.setReport('unreachable')
  const result = await payOnce({ approve: w.approve, send: w.send, sent: w.sent, store })
  assert.equal(result.status, 'unrecorded')
  assert.equal(w.sends.length, 1)
  assert.equal(store.load().length, 1, 'the hash is kept for a retry')
  w.setReport('ok')
  if (result.status !== 'unrecorded') return
  const payment = await record(store, result.pending, w.sent)
  assert.equal(payment.tx_hash, HASH)
  assert.equal(w.sends.length, 1, 'retrying never sends again')
  assert.equal(store.load().length, 0)
})

test('the server saved it but the response was lost: the retry reports the same hash', async () => {
  const w = world()
  const store = memoryStore()
  w.setReport('lost-response')
  const result = await payOnce({ approve: w.approve, send: w.send, sent: w.sent, store })
  assert.equal(result.status, 'unrecorded')
  assert.equal(w.recorded.get('p1'), HASH, 'the server already has it')
  w.setReport('ok')
  if (result.status !== 'unrecorded') return
  await record(store, result.pending, w.sent)
  assert.deepEqual([...w.recorded.values()], [HASH])
  assert.equal(w.sends.length, 1)
})

test('the page is refreshed before the report: the next page load reports from storage', async () => {
  const w = world()
  const store = memoryStore()
  w.setReport('unreachable')
  await payOnce({ approve: w.approve, send: w.send, sent: w.sent, store })
  // a new page load: only the stored text survives
  const reloaded = memoryStore()
  reloaded.raw = store.raw
  w.setReport('ok')
  for (const pending of reloaded.load()) await record(reloaded, pending, w.sent)
  assert.equal(w.recorded.get('p1'), HASH)
  assert.equal(reloaded.load().length, 0)
  assert.equal(w.sends.length, 1)
})

test('declining in the wallet sends nothing and keeps nothing to report', async () => {
  const w = world()
  const store = memoryStore()
  const declined = async (): Promise<`0x${string}`> => {
    throw Object.assign(new Error('User rejected the request.'), { code: 4001 })
  }
  await assert.rejects(payOnce({ approve: w.approve, send: declined, sent: w.sent, store }))
  assert.equal(store.load().length, 0)
  assert.equal(w.recorded.size, 0)
})
