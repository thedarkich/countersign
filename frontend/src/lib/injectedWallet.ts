import { useCallback, useEffect, useState } from 'react'
import { getAddress, stringToHex } from 'viem'

// The Wallet page talks to the browser wallet directly (EIP-1193) instead of through a cached connection
// state: it knows an address only after the wallet hands one over in this visit.

export interface Eip1193 {
  request(args: { method: string; params?: unknown }): Promise<unknown>
  on?(event: string, listener: (...args: never[]) => void): void
  removeListener?(event: string, listener: (...args: never[]) => void): void
}

export interface DiscoveredWallet {
  id: string
  name: string
  icon?: string
  provider: Eip1193
}

export const CHAINS = {
  677: { chainName: 'BOT Chain', nativeCurrency: { name: 'BOT', symbol: 'BOT', decimals: 18 }, rpcUrls: ['https://rpc.botchain.ai'], blockExplorerUrls: ['https://scan.botchain.ai'] },
  968: { chainName: 'BOT Chain Testnet', nativeCurrency: { name: 'tBOT', symbol: 'tBOT', decimals: 18 }, rpcUrls: ['https://rpc.bohr.life'], blockExplorerUrls: ['https://scan.bohr.life'] },
} as const

export type ChainId = keyof typeof CHAINS

const code = (e: unknown) => {
  const error = e as { code?: number; data?: { originalError?: { code?: number } } }
  return error?.code ?? error?.data?.originalError?.code
}
export const isRejection = (e: unknown) => code(e) === 4001 || /reject|denied|cancel/i.test(String((e as Error)?.message ?? ''))

/** EIP-6963: every installed wallet announces itself; a lone window.ethereum is the fallback. */
export function useDiscoveredWallets(): DiscoveredWallet[] {
  const [wallets, setWallets] = useState<DiscoveredWallet[]>([])
  useEffect(() => {
    const seen = new Map<string, DiscoveredWallet>()
    const announce = (event: Event) => {
      const { info, provider } = (event as CustomEvent).detail ?? {}
      if (!info?.uuid || !provider) return
      seen.set(info.uuid, { id: info.uuid, name: info.name, icon: info.icon, provider })
      setWallets([...seen.values()])
    }
    window.addEventListener('eip6963:announceProvider', announce)
    window.dispatchEvent(new Event('eip6963:requestProvider'))
    const fallback = setTimeout(() => {
      const legacy = (window as { ethereum?: Eip1193 }).ethereum
      if (!seen.size && legacy) setWallets([{ id: 'injected', name: '', provider: legacy }])
    }, 600)
    return () => {
      window.removeEventListener('eip6963:announceProvider', announce)
      clearTimeout(fallback)
    }
  }, [])
  return wallets
}

export function useInjectedWallet() {
  const [wallet, setWallet] = useState<DiscoveredWallet | null>(null)
  const [address, setAddress] = useState<`0x${string}` | null>(null)
  const [chainId, setChainId] = useState<number | null>(null)

  useEffect(() => {
    const provider = wallet?.provider
    if (!provider?.on) return
    const accounts = (list: string[]) => setAddress(list?.[0] ? getAddress(list[0]) : null)
    const chain = (id: string) => setChainId(parseInt(id, 16))
    provider.on('accountsChanged', accounts as never)
    provider.on('chainChanged', chain as never)
    return () => {
      provider.removeListener?.('accountsChanged', accounts as never)
      provider.removeListener?.('chainChanged', chain as never)
    }
  }, [wallet])

  const connect = useCallback(async (candidate: DiscoveredWallet) => {
    try {
      // ask which account to share instead of silently reusing the last one
      await candidate.provider.request({ method: 'wallet_requestPermissions', params: [{ eth_accounts: {} }] })
    } catch (e) {
      if (isRejection(e)) throw e // wallets without this method fall through to the normal prompt
    }
    const accounts = (await candidate.provider.request({ method: 'eth_requestAccounts' })) as string[]
    if (!accounts?.[0]) throw new Error('The wallet did not share an account.')
    const chain = (await candidate.provider.request({ method: 'eth_chainId' })) as string
    setWallet(candidate)
    setAddress(getAddress(accounts[0]))
    setChainId(parseInt(chain, 16))
  }, [])

  const disconnect = useCallback(async (revoke = false) => {
    if (revoke && wallet) {
      try {
        await wallet.provider.request({ method: 'wallet_revokePermissions', params: [{ eth_accounts: {} }] })
      } catch {
        /* older wallets keep the site permission; forgetting it here is enough */
      }
    }
    setWallet(null)
    setAddress(null)
    setChainId(null)
  }, [wallet])

  const ensureChain = useCallback(async (id: ChainId) => {
    if (!wallet) throw new Error('Connect a wallet first.')
    const hex = '0x' + id.toString(16)
    try {
      await wallet.provider.request({ method: 'wallet_switchEthereumChain', params: [{ chainId: hex }] })
    } catch (e) {
      if (code(e) !== 4902 && !/unrecognized|not been added|unknown chain/i.test(String((e as Error)?.message ?? ''))) throw e
      await wallet.provider.request({ method: 'wallet_addEthereumChain', params: [{ chainId: hex, ...CHAINS[id] }] })
    }
    setChainId(parseInt((await wallet.provider.request({ method: 'eth_chainId' })) as string, 16))
  }, [wallet])

  const sign = useCallback(async (message: string) => {
    if (!wallet || !address) throw new Error('Connect a wallet first.')
    return (await wallet.provider.request({ method: 'personal_sign', params: [stringToHex(message), address] })) as string
  }, [wallet, address])

  const send = useCallback(async (tx: { to: string; value: string }) => {
    if (!wallet || !address) throw new Error('Connect a wallet first.')
    const hash = await wallet.provider.request({
      method: 'eth_sendTransaction',
      params: [{ from: address, to: tx.to, value: '0x' + BigInt(tx.value).toString(16) }],
    })
    return hash as `0x${string}`
  }, [wallet, address])

  return { wallet, address, chainId, connect, disconnect, ensureChain, sign, send }
}

export type InjectedWallet = ReturnType<typeof useInjectedWallet>

/** Balance straight from the public RPC, independent of which chain the wallet is on. */
export async function rpcBalance(chain: ChainId, address: string): Promise<bigint> {
  const res = await fetch(CHAINS[chain].rpcUrls[0], {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'eth_getBalance', params: [address, 'latest'] }),
  })
  const body = await res.json()
  if (!body?.result) throw new Error('Balance unavailable')
  return BigInt(body.result)
}
