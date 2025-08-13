# 🏗️ Enhanced OI Monitor - Data Pipeline Architecture

## 📊 System Overview

The Enhanced OI Monitor is a sophisticated real-time options trading analysis system with dual AI pattern architecture, supporting multiple market segments (NFO, MCX, NSE) and comprehensive data processing pipelines.

---

## 🎯 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    ENHANCED OI MONITOR - DATA PIPELINE ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                           🚀 SYSTEM INITIALIZATION                                           │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Interactive   │    │   Environment   │    │   API Auth &    │    │   Instrument    │
│   Selection     │───▶│   Configuration │───▶│   Session Mgmt  │───▶│   Fetch & Map   │
│   (NFO/MCX/NSE) │    │   (Secrets)     │    │   (SmartConnect)│    │   (124K+ items) │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │
         ▼                       ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                           📡 DATA INGESTION LAYER                                            │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   SmartConnect  │    │  SmartWebSocket │    │   Real-time     │    │   Historical    │
│   REST API      │───▶│   V2 Feed       │───▶│   Tick Cache    │───▶│   Data Store    │
│   (LTP/OI/Greeks)│   │   (Ultra-low    │    │   (Thread-safe) │    │   (Rolling)     │
│                  │   │   latency)      │    │                  │    │                  │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │
         ▼                       ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                           🔄 DUAL AI PATTERN ARCHITECTURE                                    │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                           🤖 MINIMAL AI LOOP (Every 1s)                                      │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Tick Cache    │───▶│   Spot Price    │───▶│   PCR Calc      │───▶│   Minimal AI    │───▶│   Quick Decision│
│   (LTP/Bid/Ask) │    │   Extraction    │    │   (Put-Call     │    │   (GPT-4o-mini) │    │   (ENTER/HOLD/  │
│                  │    │   (NIFTY Spot) │    │   Ratio)        │    │   (Fast)        │    │   EXIT/WAIT)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │                       │
         ▼                       ▼                       ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                           📊 RICH AI LOOP (OI Changes)                                       │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   OI History    │───▶│   Change        │───▶│   Option Chain  │───▶│   Market        │───▶│   Rich AI       │
│   (Rolling)     │    │   Detection     │    │   Snapshot      │    │   Analysis      │    │   Coach         │
│                  │    │   (Threshold)   │    │   (Full Data)   │    │   (PCR/MP/S-R)  │    │   (Qwen-72B)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │                       │
         ▼                       ▼                       ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                           📈 DATA PROCESSING & ANALYSIS                                      │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   OI Analysis   │───▶│   Strike        │───▶│   Market        │───▶│   Trading       │───▶│   Position      │
│   (Patterns)    │    │   Verdicts      │    │   Direction     │    │   Signals       │    │   Coaching      │
│   (Long/Short   │    │   (Bull/Bear/   │    │   (BULLISH/     │    │   (BUY/SELL/    │    │   (ENTER/HOLD/  │
│   Buildup)      │    │   Neutral)      │    │   BEARISH)      │    │   HOLD)         │    │   EXIT)         │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │                       │
         ▼                       ▼                       ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                           📊 OUTPUT & VISUALIZATION                                          │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Console       │───▶│   Telegram      │───▶│   SQLite        │───▶│   Log Files     │───▶│   AI Logs       │
│   Table Output  │    │   (Images +     │    │   (Paper        │    │   (System       │    │   (NDJSON +     │
│   (Formatted)   │    │   Messages)     │    │   Trading)      │    │   Events)       │    │   TXT)          │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                           🔧 SUPPORTING INFRASTRUCTURE                                       │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Threading     │    │   Error         │    │   Rate          │    │   Memory        │    │   Heartbeat     │
│   (Concurrent   │    │   Handling      │    │   Limiting      │    │   Management    │    │   Monitoring    │
│   Processing)   │    │   (Graceful)    │    │   (API Calls)   │    │   (Cache)       │    │   (Health)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## 🔄 Detailed Data Flow

### 1. **System Initialization**
```
User Selection → Environment Config → API Authentication → Instrument Mapping
     ↓              ↓                    ↓                    ↓
Interactive    Secrets from      SmartConnect     124K+ Instruments
Market Choice   Environment      Session Token    Token Mapping
```

### 2. **Data Ingestion Pipeline**
```
SmartConnect API → WebSocket V2 → Tick Cache → Historical Store
     ↓              ↓              ↓            ↓
REST Calls      Real-time Feed   Thread-safe   Rolling Buffer
(LTP/OI)        (Ultra-low       Cache         (30min history)
                latency)
```

### 3. **Dual AI Pattern**

#### **Minimal AI Loop (Every 1 Second)**
```
Tick Cache → Spot Price → PCR Calc → Minimal AI → Quick Decision
     ↓           ↓           ↓           ↓           ↓
LTP/Bid/Ask   NIFTY Spot   Put-Call    GPT-4o-mini  ENTER/HOLD/
              Extraction   Ratio       (Fast)       EXIT/WAIT
```

#### **Rich AI Loop (Based on OI Changes)**
```
OI History → Change Detection → Option Chain → Market Analysis → Rich AI
     ↓            ↓               ↓              ↓              ↓
Rolling      Threshold-based   Full Snapshot   PCR/MP/S-R    Qwen-72B
Buffer       (10% symbols)     (Complete)      Analysis      (Deep)
```

### 4. **Data Processing & Analysis**
```
OI Analysis → Strike Verdicts → Market Direction → Trading Signals → Position Coaching
     ↓            ↓               ↓                ↓                ↓
Patterns      Bull/Bear/      BULLISH/         BUY/SELL/        ENTER/HOLD/
(Long/Short   Neutral         BEARISH         HOLD             EXIT
Buildup)
```

### 5. **Output & Visualization**
```
Console → Telegram → SQLite → Log Files → AI Logs
   ↓         ↓         ↓         ↓         ↓
Formatted   Images +   Paper     System    NDJSON +
Table       Messages   Trading   Events    TXT
```

---

## 🏗️ Component Architecture

### **Core Components**

1. **SmartConnect API Client**
   - REST API for market data
   - Session management
   - Authentication (TOTP)

2. **SmartWebSocket V2**
   - Ultra-low latency tick streaming
   - Real-time LTP, Bid, Ask, Volume
   - Multi-exchange support (NSE, NFO, MCX)

3. **Dual AI Pattern**
   - **Minimal AI**: Fast decisions every 1s (GPT-4o-mini)
   - **Rich AI**: Deep analysis on OI changes (Qwen-72B)

4. **Data Processing Engine**
   - OI pattern analysis
   - Strike verdicts
   - Market direction calculation
   - Trading signal generation

5. **Output Systems**
   - Console table formatting
   - Telegram integration
   - SQLite logging
   - File-based logging

### **Data Structures**

1. **Tick Cache** (`TICKS_CACHE`)
   ```python
   {
       "symbol": {
           "ltp": float,
           "bid": float,
           "ask": float,
           "volume": int,
           "timestamp": float
       }
   }
   ```

2. **OI History** (`RollingTicks`)
   ```python
   {
       "symbol": deque([
           {"ts": timestamp, "ltp": price, "oi": open_interest}
       ], maxlen=MAX_POINTS)
   }
   ```

3. **Market Analysis**
   ```python
   {
       "direction": "BULLISH/BEARISH/NEUTRAL",
       "confidence_factor": float,
       "pcr": float,
       "max_pain": int,
       "support": [(strike, strength)],
       "resistance": [(strike, strength)]
   }
   ```

---

## 🔄 Threading Architecture

### **Concurrent Threads**

1. **Main Thread**
   - System orchestration
   - Heartbeat monitoring
   - User interaction

2. **WebSocket Thread**
   - Real-time data streaming
   - Tick processing
   - Connection management

3. **Minimal AI Thread** (`_coach_sampler_loop`)
   - Runs every 1 second
   - Quick decision making
   - Position coaching

4. **Rich AI Thread** (`_snapshot_loop`)
   - Triggered by OI changes
   - Deep market analysis
   - Comprehensive insights

### **Thread Safety**
- `WS_LOCK`: WebSocket data access
- `LOG_LOCK`: Logging operations
- Thread-safe data structures
- Atomic operations

---

## 📊 Market Segment Support

### **NFO Mode (NIFTY Options)**
- ✅ Full AI analysis
- ✅ OI table with verdicts
- ✅ PCR calculations
- ✅ Telegram integration
- ✅ Dual AI pattern

### **MCX Mode (Commodities)**
- ✅ Tick streaming only
- ✅ Multiple commodities
- ❌ No AI analysis
- ❌ No OI analysis

### **NSE Mode (Equity)**
- ✅ Basic tick streaming
- ❌ No options analysis
- ❌ Limited features

---

## 🔧 Configuration & Environment

### **Environment Variables**
```bash
FEED_SEGMENT=NFO/MCX/NSE
MCX_NAME=SILVERMIC/GOLDMIC/COPPER
TELEGRAM_BOT_TOKEN=your_token
OPENROUTER_API_KEY=your_key
```

### **Interactive Selection**
- Market segment choice
- MCX commodity selection
- Default fallbacks

---

## 📈 Performance Characteristics

### **Latency**
- WebSocket: Ultra-low latency (< 1ms)
- Minimal AI: 1-second intervals
- Rich AI: Triggered by changes

### **Throughput**
- 124K+ instruments processed
- Real-time tick streaming
- Concurrent AI processing

### **Memory Usage**
- Rolling buffers (30min history)
- Thread-safe caches
- Efficient data structures

---

## 🛡️ Error Handling & Resilience

### **Graceful Degradation**
- API failures → Fallback modes
- WebSocket disconnects → Auto-reconnect
- AI failures → Rule-based fallbacks

### **Monitoring**
- Heartbeat monitoring
- Health checks
- Error logging

### **Recovery**
- Automatic reconnection
- State restoration
- Data consistency

---

## 🎯 Key Features

1. **Dual AI Pattern**: Fast + Deep analysis
2. **Multi-Market Support**: NFO, MCX, NSE
3. **Real-time Processing**: Ultra-low latency
4. **Comprehensive Analysis**: OI, PCR, Max Pain
5. **Rich Output**: Console, Telegram, Logs
6. **Interactive Selection**: User-friendly setup
7. **Thread-safe Architecture**: Concurrent processing
8. **Error Resilience**: Graceful degradation

---

## 🚀 Usage Examples

### **NFO Mode (Default)**
```bash
py Enhanced_OI_Monitor_CLEAN.py
# Select: 1 (NFO)
```

### **MCX Mode**
```bash
py Enhanced_OI_Monitor_CLEAN.py
# Select: 2 (MCX)
# Select: 1 (SILVERMIC)
```

### **Environment Variables**
```bash
$env:FEED_SEGMENT='NFO'
$env:MCX_NAME='GOLDMIC'
py Enhanced_OI_Monitor_CLEAN.py
```

---

This architecture provides a robust, scalable, and feature-rich platform for real-time options trading analysis with intelligent AI-driven insights and comprehensive market monitoring capabilities.
