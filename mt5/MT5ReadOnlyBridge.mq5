#property strict
#property version   "3.610"
#property description "Read-only account/position/risk/history export for COT Research."
#property description "Contains no OrderSend, trade modification or close logic."

input int RefreshSeconds = 2;
input int SymbolCatalogRefreshSeconds = 60;

datetime g_last_symbol_catalog_export = 0;

string ACCOUNT_FILE   = "cot_mt5_account.csv";
string POSITIONS_FILE = "cot_mt5_positions.csv";
string SYMBOLS_FILE   = "cot_mt5_symbols.csv";

// Returns the beginning of the current FTMO/MT5 server day. FTMO documents
// MetaTrader server time as GMT+2 + DST, i.e. the CE(S)T day boundary used by
// the 2-Step Maximum Daily Loss rule.
datetime ServerDayStart(datetime server_now)
{
   MqlDateTime dt={};
   TimeToStruct(server_now, dt);
   dt.hour=0;
   dt.min=0;
   dt.sec=0;
   return StructToTime(dt);
}

// Net balance movement since 00:00 server time. History deals expose profit,
// commission, swap and fee separately. Summing all deal balance effects lets
// us reconstruct the account balance recorded at the daily reset.
double DailyRealizedPnl(datetime server_now)
{
   datetime day_start=ServerDayStart(server_now);
   if(!HistorySelect(day_start, server_now))
   {
      Print("COT MT5 Bridge: HistorySelect failed: ", GetLastError());
      return 0.0;
   }

   double total=0.0;
   int deals=HistoryDealsTotal();
   for(int i=0; i<deals; i++)
   {
      ulong ticket=HistoryDealGetTicket(i);
      if(ticket==0)
         continue;
      total += HistoryDealGetDouble(ticket, DEAL_PROFIT);
      total += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      total += HistoryDealGetDouble(ticket, DEAL_SWAP);
      total += HistoryDealGetDouble(ticket, DEAL_FEE);
   }
   return total;
}

void WriteAccountSnapshot()
{
   int handle=FileOpen(
      ACCOUNT_FILE,
      FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ,
      ';'
   );
   if(handle==INVALID_HANDLE)
   {
      Print("COT MT5 Bridge: account file open failed: ", GetLastError());
      return;
   }

   datetime server_now=TimeTradeServer();
   if(server_now<=0)
      server_now=TimeCurrent();

   double daily_realized=DailyRealizedPnl(server_now);
   double balance=AccountInfoDouble(ACCOUNT_BALANCE);
   double day_start_balance=balance-daily_realized;

   FileWrite(
      handle,
      "timestamp_unix", "server_time_unix", "login", "server", "name", "company", "currency",
      "balance", "equity", "profit", "margin", "margin_free", "margin_level",
      "leverage", "trade_allowed", "trade_expert", "day_start_balance", "daily_realized_pnl"
   );

   FileWrite(
      handle,
      (long)server_now,
      (long)server_now,
      (long)AccountInfoInteger(ACCOUNT_LOGIN),
      AccountInfoString(ACCOUNT_SERVER),
      AccountInfoString(ACCOUNT_NAME),
      AccountInfoString(ACCOUNT_COMPANY),
      AccountInfoString(ACCOUNT_CURRENCY),
      balance,
      AccountInfoDouble(ACCOUNT_EQUITY),
      AccountInfoDouble(ACCOUNT_PROFIT),
      AccountInfoDouble(ACCOUNT_MARGIN),
      AccountInfoDouble(ACCOUNT_MARGIN_FREE),
      AccountInfoDouble(ACCOUNT_MARGIN_LEVEL),
      (long)AccountInfoInteger(ACCOUNT_LEVERAGE),
      (long)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED),
      (long)AccountInfoInteger(ACCOUNT_TRADE_EXPERT),
      day_start_balance,
      daily_realized
   );

   FileFlush(handle);
   FileClose(handle);
}

void WritePositionsSnapshot()
{
   int handle=FileOpen(
      POSITIONS_FILE,
      FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ,
      ';'
   );
   if(handle==INVALID_HANDLE)
   {
      Print("COT MT5 Bridge: positions file open failed: ", GetLastError());
      return;
   }

   FileWrite(
      handle,
      "ticket", "symbol", "side", "volume", "price_open", "sl", "tp",
      "price_current", "profit", "swap", "time", "comment",
      "contract_size", "tick_size", "tick_value", "tick_value_profit", "tick_value_loss",
      "point", "digits", "volume_min", "volume_max", "volume_step", "currency_base",
      "currency_profit", "currency_margin", "swap_long", "swap_short"
   );

   int total=PositionsTotal();
   for(int i=0; i<total; i++)
   {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket))
         continue;

      string symbol=PositionGetString(POSITION_SYMBOL);
      ENUM_POSITION_TYPE ptype=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      string side=ptype==POSITION_TYPE_BUY ? "LONG" : "SHORT";

      FileWrite(
         handle,
         (long)ticket,
         symbol,
         side,
         PositionGetDouble(POSITION_VOLUME),
         PositionGetDouble(POSITION_PRICE_OPEN),
         PositionGetDouble(POSITION_SL),
         PositionGetDouble(POSITION_TP),
         PositionGetDouble(POSITION_PRICE_CURRENT),
         PositionGetDouble(POSITION_PROFIT),
         PositionGetDouble(POSITION_SWAP),
         (long)PositionGetInteger(POSITION_TIME),
         PositionGetString(POSITION_COMMENT),
         SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE),
         SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE),
         SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE),
         SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE_PROFIT),
         SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE_LOSS),
         SymbolInfoDouble(symbol, SYMBOL_POINT),
         (long)SymbolInfoInteger(symbol, SYMBOL_DIGITS),
         SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN),
         SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX),
         SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP),
         SymbolInfoString(symbol, SYMBOL_CURRENCY_BASE),
         SymbolInfoString(symbol, SYMBOL_CURRENCY_PROFIT),
         SymbolInfoString(symbol, SYMBOL_CURRENCY_MARGIN),
         SymbolInfoDouble(symbol, SYMBOL_SWAP_LONG),
         SymbolInfoDouble(symbol, SYMBOL_SWAP_SHORT)
      );
   }

   FileFlush(handle);
   FileClose(handle);
}

void WriteSymbolCatalog()
{
   int handle=FileOpen(
      SYMBOLS_FILE,
      FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ,
      ';'
   );
   if(handle==INVALID_HANDLE)
   {
      Print("COT MT5 Bridge: symbols file open failed: ", GetLastError());
      return;
   }

   FileWrite(
      handle,
      "symbol", "description", "path", "selected", "visible", "trade_mode", "can_open",
      "bid", "ask", "last", "contract_size", "tick_size", "tick_value",
      "tick_value_profit", "tick_value_loss", "point", "digits", "volume_min", "volume_max",
      "volume_step", "currency_base", "currency_profit", "currency_margin", "swap_long", "swap_short"
   );

   // false = complete broker-side symbol universe, not only Market Watch.
   int total=SymbolsTotal(false);
   for(int i=0; i<total; i++)
   {
      string symbol=SymbolName(i, false);
      if(symbol=="")
         continue;

      ENUM_SYMBOL_TRADE_MODE trade_mode=(ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE);
      bool can_open=(trade_mode==SYMBOL_TRADE_MODE_FULL ||
                     trade_mode==SYMBOL_TRADE_MODE_LONGONLY ||
                     trade_mode==SYMBOL_TRADE_MODE_SHORTONLY);

      FileWrite(
         handle,
         symbol,
         SymbolInfoString(symbol, SYMBOL_DESCRIPTION),
         SymbolInfoString(symbol, SYMBOL_PATH),
         (long)SymbolInfoInteger(symbol, SYMBOL_SELECT),
         (long)SymbolInfoInteger(symbol, SYMBOL_VISIBLE),
         (long)trade_mode,
         (long)can_open,
         SymbolInfoDouble(symbol, SYMBOL_BID),
         SymbolInfoDouble(symbol, SYMBOL_ASK),
         SymbolInfoDouble(symbol, SYMBOL_LAST),
         SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE),
         SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE),
         SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE),
         SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE_PROFIT),
         SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE_LOSS),
         SymbolInfoDouble(symbol, SYMBOL_POINT),
         (long)SymbolInfoInteger(symbol, SYMBOL_DIGITS),
         SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN),
         SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX),
         SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP),
         SymbolInfoString(symbol, SYMBOL_CURRENCY_BASE),
         SymbolInfoString(symbol, SYMBOL_CURRENCY_PROFIT),
         SymbolInfoString(symbol, SYMBOL_CURRENCY_MARGIN),
         SymbolInfoDouble(symbol, SYMBOL_SWAP_LONG),
         SymbolInfoDouble(symbol, SYMBOL_SWAP_SHORT)
      );
   }

   g_last_symbol_catalog_export=TimeLocal();

   FileFlush(handle);
   FileClose(handle);
}

void ExportLiveSnapshot()
{
   WriteAccountSnapshot();
   WritePositionsSnapshot();
}

void MaybeRefreshSymbolCatalog(bool force=false)
{
   int seconds=MathMax(10, SymbolCatalogRefreshSeconds);
   datetime now=TimeLocal();
   if(force || g_last_symbol_catalog_export<=0 || (now-g_last_symbol_catalog_export)>=seconds)
      WriteSymbolCatalog();
}


ENUM_TIMEFRAMES ParseHistoryTimeframe(string text)
{
   StringToUpper(text);
   if(text=="M1") return PERIOD_M1;
   if(text=="M5") return PERIOD_M5;
   if(text=="M15") return PERIOD_M15;
   if(text=="H1") return PERIOD_H1;
   if(text=="D1") return PERIOD_D1;
   return PERIOD_CURRENT;
}

void WriteHistoryError(string request_id, string message)
{
   string response="cot_history_response_"+request_id+".csv";
   int out=FileOpen(response, FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ, ';');
   if(out==INVALID_HANDLE)
      return;
   FileWrite(out, "request_id", "status", "error", "time_unix", "open", "high", "low", "close", "tick_volume", "spread", "real_volume");
   FileWrite(out, request_id, "ERROR", message, 0, 0, 0, 0, 0, 0, 0, 0);
   FileFlush(out);
   FileClose(out);
}

void ProcessHistoryRequest(string filename)
{
   int in=FileOpen(filename, FILE_READ|FILE_CSV|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ, ';');
   if(in==INVALID_HANDLE)
      return;

   // Header
   for(int i=0; i<5 && !FileIsEnding(in); i++)
      FileReadString(in);

   string request_id=FileReadString(in);
   string symbol=FileReadString(in);
   long from_unix=(long)StringToInteger(FileReadString(in));
   long to_unix=(long)StringToInteger(FileReadString(in));
   string tf_text=FileReadString(in);
   FileClose(in);

   if(request_id=="" || symbol=="" || from_unix<=0 || to_unix<=from_unix)
   {
      WriteHistoryError(request_id, "invalid request");
      FileDelete(filename, FILE_COMMON);
      return;
   }

   ENUM_TIMEFRAMES timeframe=ParseHistoryTimeframe(tf_text);
   if(timeframe==PERIOD_CURRENT)
   {
      WriteHistoryError(request_id, "unsupported timeframe");
      FileDelete(filename, FILE_COMMON);
      return;
   }

   // Selecting a symbol only exposes its history to the local terminal; no trade request is sent.
   SymbolSelect(symbol, true);
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   ResetLastError();
   int copied=CopyRates(symbol, timeframe, (datetime)from_unix, (datetime)to_unix, rates);
   int err=GetLastError();

   // CopyRates can return -1 while the terminal is still synchronizing history.
   // Keep the request file so the next timer tick retries instead of manufacturing a failure.
   if(copied<0)
   {
      Print("COT MT5 Bridge: history not ready yet for ", symbol, " ", tf_text, " code=", err);
      return;
   }

   string response="cot_history_response_"+request_id+".csv";
   int out=FileOpen(response, FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ, ';');
   if(out==INVALID_HANDLE)
      return;

   FileWrite(out, "request_id", "status", "error", "time_unix", "open", "high", "low", "close", "tick_volume", "spread", "real_volume");
   if(copied==0)
   {
      FileWrite(out, request_id, "OK", "", "", "", "", "", "", "", "", "");
   }
   else
   {
      for(int i=0; i<copied; i++)
      {
         FileWrite(
            out,
            request_id,
            "OK",
            "",
            (long)rates[i].time,
            rates[i].open,
            rates[i].high,
            rates[i].low,
            rates[i].close,
            (long)rates[i].tick_volume,
            (long)rates[i].spread,
            (long)rates[i].real_volume
         );
      }
   }
   FileFlush(out);
   FileClose(out);
   FileDelete(filename, FILE_COMMON);
}

void ProcessHistoryRequests()
{
   string filename="";
   long search=FileFindFirst("cot_history_request_*.csv", filename, FILE_COMMON);
   if(search==INVALID_HANDLE)
      return;
   do
   {
      if(filename!="")
         ProcessHistoryRequest(filename);
   }
   while(FileFindNext(search, filename));
   FileFindClose(search);
}

int OnInit()
{
   int seconds=MathMax(1, RefreshSeconds);
   EventSetTimer(seconds);
   Print("COT MT5 Bridge V3.6.1 active. Full broker CFD catalog + read-only history service. Common data path: ", TerminalInfoString(TERMINAL_COMMONDATA_PATH));
   ExportLiveSnapshot();
   MaybeRefreshSymbolCatalog(true);
   ProcessHistoryRequests();
   return(INIT_SUCCEEDED);
}

void OnTimer()
{
   ExportLiveSnapshot();
   MaybeRefreshSymbolCatalog(false);
   ProcessHistoryRequests();
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}
