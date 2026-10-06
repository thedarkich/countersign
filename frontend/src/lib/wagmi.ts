import { createConfig, http } from 'wagmi'
import { injected } from 'wagmi/connectors'
import { defineChain } from 'viem'

// BOT Chain has no EIP-1559: every write from Controls is sent as a legacy transaction.
export const botChain = defineChain({
  id: 677,
  name: 'BOT Chain',
  nativeCurrency: { name: 'BOT', symbol: 'BOT', decimals: 18 },
  rpcUrls: { default: { http: ['https://rpc.botchain.ai'], webSocket: ['wss://ws-rpc.botchain.ai'] } },
  blockExplorers: { default: { name: 'BOT Chain Explorer', url: 'https://scan.botchain.ai' } },
})

export const botTestnet = defineChain({
  id: 968,
  name: 'BOT Chain Testnet',
  nativeCurrency: { name: 'tBOT', symbol: 'tBOT', decimals: 18 },
  rpcUrls: { default: { http: ['https://rpc.bohr.life'] } },
  blockExplorers: { default: { name: 'BOT Chain Testnet Explorer', url: 'https://scan.bohr.life' } },
  testnet: true,
})

export const wagmiConfig = createConfig({
  chains: [botChain, botTestnet],
  connectors: [injected()],
  transports: {
    [botChain.id]: http(),
    [botTestnet.id]: http(),
  },
})

declare module 'wagmi' {
  interface Register {
    config: typeof wagmiConfig
  }
}
