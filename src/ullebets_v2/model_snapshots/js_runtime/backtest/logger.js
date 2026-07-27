let clientStepCounter = 0;
let serverStepCounter = 0;

function formatMessage(step, message, context) {
  const prefix = `${step}. ${message}`;
  return context ? `${prefix} (${context})` : prefix;
}

function emitLog(method, message, data) {
  if (data !== undefined) {
    method(message, data);
  } else {
    method(message);
  }
}

export function logClientBacktestStep(message, data, context) {
  clientStepCounter += 1;
  const text = formatMessage(clientStepCounter, message, context);
  emitLog(console.log, text, data);
  return clientStepCounter;
}

export function logClientBacktestError(message, data, context) {
  clientStepCounter += 1;
  const text = formatMessage(clientStepCounter, message, context);
  emitLog(console.error, text, data);
  return clientStepCounter;
}

export function resetClientBacktestSteps(reason, data, context) {
  clientStepCounter = 0;
  const message = reason
    ? `Backtestflödet startar – ${reason}`
    : "Backtestflödet startar.";
  return logClientBacktestStep(message, data, context);
}

export function logServerBacktestStep(message, data, context) {
  serverStepCounter += 1;
  const text = formatMessage(serverStepCounter, message, context);
  emitLog(console.log, text, data);
  return serverStepCounter;
}

export function logServerBacktestError(message, data, context) {
  serverStepCounter += 1;
  const text = formatMessage(serverStepCounter, message, context);
  emitLog(console.error, text, data);
  return serverStepCounter;
}

export function resetServerBacktestSteps(reason, data, context) {
  serverStepCounter = 0;
  const message = reason
    ? `Serverflödet startar – ${reason}`
    : "Serverflödet startar.";
  return logServerBacktestStep(message, data, context);
}
