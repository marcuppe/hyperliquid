# Trading scripts

These scripts sign and submit orders to Hyperliquid. They require a private key.

## Before running anything here

1. **Read** [../../references/trading.md](../../references/trading.md).
2. **Use an agent wallet, not your master key.** Create one at https://app.hyperliquid.xyz/API.
3. **Stay on testnet** until you have a clear reason to switch. Testnet USDC is free at https://app.hyperliquid-testnet.xyz/drip.

## Install

```bash
pip install hyperliquid-python-sdk
```

## Configure

```bash
export HL_ENV=testnet                       # or "mainnet" when you mean it
export HL_PRIVATE_KEY=0x<agent_key>
export HL_ACCOUNT_ADDRESS=0x<master_address>  # only if HL_PRIVATE_KEY is an agent wallet
```

`HL_ACCOUNT_ADDRESS` is how the SDK knows who the agent is trading on behalf of. If you're (unwisely) running with the master key itself, you can omit it.

## Scripts

| Script              | Action                                             |
|---------------------|----------------------------------------------------|
| `place_order.py`    | Place a single limit order                         |
| `cancel_order.py`   | Cancel an order by `oid`                           |

Every script:
- Defaults to testnet.
- Prints the exact action it's about to submit.
- On `HL_ENV=mainnet`, asks for explicit `yes` confirmation before signing.
- Prints the full API response (including `oid`) so you can track the order.

## Safety

These scripts **do not retry on error**. If an exchange call fails, they surface the error and exit. A blind retry with the same action can double-fill — look at the response, decide what to do, then run the script again with a fresh nonce.
