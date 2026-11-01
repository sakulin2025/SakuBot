export const promptVariables = [
  ['owner_qq_id', '主人 QQ 号'],
  ['bot_qq_id', '机器人 QQ 号'],
  ['session_id', '会话 ID'],
  ['session_type', '会话类型'],
  ['session_qq_id', '群号或私聊 QQ 号'],
  ['sender_qq_id', '发送者 QQ 号'],
  ['sender_name', '发送者名称'],
] as const;
export const variableName = (name: string) => `{{ ${name} }}`;
