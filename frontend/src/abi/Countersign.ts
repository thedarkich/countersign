// Hand-written from docs/SPEC.md §2 so the frontend can be built before the contract exists.
// Once `forge build` has run, `npm run abi` overwrites this file with the ABI from the Foundry artifact.
export const countersignAbi = [
  // time-locked (owner queues, anyone executes after the delay)
  { type: 'function', name: 'queueAddVendor', stateMutability: 'nonpayable', inputs: [{ name: 'vendorId', type: 'uint256' }, { name: 'payout', type: 'address' }], outputs: [{ name: '', type: 'bytes32' }] },
  { type: 'function', name: 'queueSetPayout', stateMutability: 'nonpayable', inputs: [{ name: 'vendorId', type: 'uint256' }, { name: 'newPayout', type: 'address' }], outputs: [{ name: '', type: 'bytes32' }] },
  {
    type: 'function',
    name: 'queueAddPO',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'poId', type: 'uint256' },
      { name: 'vendorId', type: 'uint256' },
      { name: 'cap', type: 'uint256' },
      { name: 'expiry', type: 'uint64' },
      { name: 'periodDays', type: 'uint32' },
    ],
    outputs: [{ name: '', type: 'bytes32' }],
  },
  { type: 'function', name: 'queueAddAgent', stateMutability: 'nonpayable', inputs: [{ name: 'agent', type: 'address' }], outputs: [{ name: '', type: 'bytes32' }] },
  { type: 'function', name: 'queueRaiseDailyCap', stateMutability: 'nonpayable', inputs: [{ name: 'newCap', type: 'uint256' }], outputs: [{ name: '', type: 'bytes32' }] },
  { type: 'function', name: 'queueUnpause', stateMutability: 'nonpayable', inputs: [], outputs: [{ name: '', type: 'bytes32' }] },
  { type: 'function', name: 'queueWithdraw', stateMutability: 'nonpayable', inputs: [{ name: 'amount', type: 'uint256' }], outputs: [{ name: '', type: 'bytes32' }] },
  { type: 'function', name: 'execute', stateMutability: 'nonpayable', inputs: [{ name: 'id', type: 'bytes32' }], outputs: [] },
  { type: 'function', name: 'cancel', stateMutability: 'nonpayable', inputs: [{ name: 'id', type: 'bytes32' }], outputs: [] },

  // instant
  { type: 'function', name: 'pause', stateMutability: 'nonpayable', inputs: [], outputs: [] },
  { type: 'function', name: 'deactivateVendor', stateMutability: 'nonpayable', inputs: [{ name: 'vendorId', type: 'uint256' }], outputs: [] },
  { type: 'function', name: 'closePO', stateMutability: 'nonpayable', inputs: [{ name: 'poId', type: 'uint256' }], outputs: [] },
  { type: 'function', name: 'revokeAgent', stateMutability: 'nonpayable', inputs: [{ name: 'agent', type: 'address' }], outputs: [] },
  { type: 'function', name: 'lowerDailyCap', stateMutability: 'nonpayable', inputs: [{ name: 'newCap', type: 'uint256' }], outputs: [] },

  // agent
  {
    type: 'function',
    name: 'pay',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'vendorId', type: 'uint256' },
      { name: 'payTo', type: 'address' },
      { name: 'poId', type: 'uint256' },
      { name: 'amount', type: 'uint256' },
      { name: 'invoiceHash', type: 'bytes32' },
    ],
    outputs: [{ name: 'paid', type: 'bool' }],
  },

  // views
  { type: 'function', name: 'owner', stateMutability: 'view', inputs: [], outputs: [{ name: '', type: 'address' }] },
  { type: 'function', name: 'paused', stateMutability: 'view', inputs: [], outputs: [{ name: '', type: 'bool' }] },
  { type: 'function', name: 'token', stateMutability: 'view', inputs: [], outputs: [{ name: '', type: 'address' }] },
  { type: 'function', name: 'delay', stateMutability: 'view', inputs: [], outputs: [{ name: '', type: 'uint64' }] },
  { type: 'function', name: 'dailyCap', stateMutability: 'view', inputs: [], outputs: [{ name: '', type: 'uint256' }] },
  { type: 'function', name: 'spentToday', stateMutability: 'view', inputs: [], outputs: [{ name: '', type: 'uint256' }] },
  { type: 'function', name: 'remainingToday', stateMutability: 'view', inputs: [], outputs: [{ name: '', type: 'uint256' }] },
  { type: 'function', name: 'vaultBalance', stateMutability: 'view', inputs: [], outputs: [{ name: '', type: 'uint256' }] },
  { type: 'function', name: 'isAgent', stateMutability: 'view', inputs: [{ name: '', type: 'address' }], outputs: [{ name: '', type: 'bool' }] },
  { type: 'function', name: 'invoicePaid', stateMutability: 'view', inputs: [{ name: '', type: 'bytes32' }], outputs: [{ name: '', type: 'bool' }] },
  {
    type: 'function',
    name: 'vendors',
    stateMutability: 'view',
    inputs: [{ name: '', type: 'uint256' }],
    outputs: [
      { name: 'payout', type: 'address' },
      { name: 'active', type: 'bool' },
      { name: 'exists', type: 'bool' },
    ],
  },
  {
    type: 'function',
    name: 'pos',
    stateMutability: 'view',
    inputs: [{ name: '', type: 'uint256' }],
    outputs: [
      { name: 'vendorId', type: 'uint256' },
      { name: 'cap', type: 'uint256' },
      { name: 'spent', type: 'uint256' },
      { name: 'expiry', type: 'uint64' },
      { name: 'periodDays', type: 'uint32' },
      { name: 'periodStart', type: 'uint64' },
      { name: 'exists', type: 'bool' },
      { name: 'closed', type: 'bool' },
    ],
  },
  { type: 'function', name: 'poRemaining', stateMutability: 'view', inputs: [{ name: 'poId', type: 'uint256' }], outputs: [{ name: '', type: 'uint256' }] },
  { type: 'function', name: 'changeCount', stateMutability: 'view', inputs: [], outputs: [{ name: '', type: 'uint256' }] },
  { type: 'function', name: 'changeIds', stateMutability: 'view', inputs: [{ name: '', type: 'uint256' }], outputs: [{ name: '', type: 'bytes32' }] },
  {
    type: 'function',
    name: 'getChange',
    stateMutability: 'view',
    inputs: [{ name: 'id', type: 'bytes32' }],
    outputs: [
      {
        name: '',
        type: 'tuple',
        components: [
          { name: 'kind', type: 'uint8' },
          { name: 'data', type: 'bytes' },
          { name: 'eta', type: 'uint64' },
          { name: 'executed', type: 'bool' },
          { name: 'cancelled', type: 'bool' },
        ],
      },
    ],
  },

  // events
  { type: 'event', name: 'ChangeQueued', inputs: [{ name: 'id', type: 'bytes32', indexed: true }, { name: 'kind', type: 'uint8', indexed: false }, { name: 'data', type: 'bytes', indexed: false }, { name: 'eta', type: 'uint64', indexed: false }] },
  { type: 'event', name: 'ChangeExecuted', inputs: [{ name: 'id', type: 'bytes32', indexed: true }, { name: 'kind', type: 'uint8', indexed: false }] },
  { type: 'event', name: 'ChangeCancelled', inputs: [{ name: 'id', type: 'bytes32', indexed: true }] },
  { type: 'event', name: 'VendorDeactivated', inputs: [{ name: 'vendorId', type: 'uint256', indexed: true }] },
  { type: 'event', name: 'POClosed', inputs: [{ name: 'poId', type: 'uint256', indexed: true }] },
  { type: 'event', name: 'AgentRevoked', inputs: [{ name: 'agent', type: 'address', indexed: true }] },
  { type: 'event', name: 'DailyCapLowered', inputs: [{ name: 'newCap', type: 'uint256', indexed: false }] },
  {
    type: 'event',
    name: 'Paid',
    inputs: [
      { name: 'vendorId', type: 'uint256', indexed: true },
      { name: 'poId', type: 'uint256', indexed: true },
      { name: 'agent', type: 'address', indexed: true },
      { name: 'payTo', type: 'address', indexed: false },
      { name: 'amount', type: 'uint256', indexed: false },
      { name: 'invoiceHash', type: 'bytes32', indexed: false },
    ],
  },
  {
    type: 'event',
    name: 'Blocked',
    inputs: [
      { name: 'vendorId', type: 'uint256', indexed: true },
      { name: 'poId', type: 'uint256', indexed: true },
      { name: 'agent', type: 'address', indexed: true },
      { name: 'reason', type: 'uint8', indexed: false },
      { name: 'payTo', type: 'address', indexed: false },
      { name: 'amount', type: 'uint256', indexed: false },
      { name: 'invoiceHash', type: 'bytes32', indexed: false },
    ],
  },
  { type: 'event', name: 'Paused', inputs: [{ name: 'account', type: 'address', indexed: false }] },
  { type: 'event', name: 'Unpaused', inputs: [{ name: 'account', type: 'address', indexed: false }] },
  { type: 'error', name: 'NotAgent', inputs: [] },
] as const
