import type { TranslationKey } from './translations';

export const displayNameKeys: Record<string, TranslationKey> = {
  'Start Nodes': 'display.startNodes',
  Analysts: 'display.analysts',
  Swarms: 'display.swarms',
  'End Nodes': 'display.endNodes',
  'Portfolio Input': 'display.portfolioInput',
  'Stock Input': 'display.stockInput',
  'Portfolio Manager': 'display.portfolioManager',
  'Data Wizards': 'display.dataWizards',
  'Market Mavericks': 'display.marketMavericks',
  'Value Investors': 'display.valueInvestors',
  'Technical Analyst': 'display.technicalAnalyst',
  'Fundamentals Analyst': 'display.fundamentalsAnalyst',
  'Sentiment Analyst': 'display.sentimentAnalyst',
  'Valuation Analyst': 'display.valuationAnalyst',
  'JSON Output': 'node.jsonOutput',
  'Investment Report': 'node.investmentReport',
};

export const statusKeys: Record<string, TranslationKey> = {
  IDLE: 'status.idle',
  IN_PROGRESS: 'status.inProgress',
  COMPLETE: 'status.complete',
  ERROR: 'status.error',
  Done: 'status.done',
  Checking: 'status.checking',
  idle: 'status.idle',
  in_progress: 'status.inProgress',
  complete: 'status.complete',
  error: 'status.error',
  done: 'status.done',
};

export const actionKeys: Record<string, TranslationKey> = {
  long: 'action.long',
  short: 'action.short',
  hold: 'action.hold',
  buy: 'action.buy',
  sell: 'action.sell',
  cover: 'action.cover',
  unknown: 'action.unknown',
};

export const signalKeys: Record<string, TranslationKey> = {
  bullish: 'signal.bullish',
  bearish: 'signal.bearish',
  neutral: 'signal.neutral',
  unknown: 'signal.unknown',
};
