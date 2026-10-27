# Saku UI

SakuBot 0.9 的公共 Vue 3 / TypeScript 组件。核心通过 `app.use(SakuUI)` 注册；插件通过 `mountPlugin(App)` 自动注册。也可从 `@sakubot/ui` 按名称导入。源码位于 `frontend/src/components/ui`。

## 使用

```vue
<script setup lang="ts">
import { ref, reactive, usePluginHost } from '@sakubot/ui'
const host = usePluginHost()
const busy = ref(false)
const editing = ref(false)
const draft = reactive({ name: '', enabled: true })
async function save() {
  busy.value = true
  try {
    await host.api('records', draft)
    editing.value = false
    host.toast('已保存')
  } finally { busy.value = false }
}
</script>

<template>
  <SPageHeader title="记录本">
    <SButton variant="primary" icon="plus" @click="editing = true">新增</SButton>
  </SPageHeader>
  <SDialog :open="editing" title="新增记录" @close="editing = false">
    <SForm id="record-form" :model="draft" :rules="{name:[{required:true,message:'请输入名称'}]}" @submit="save">
      <SFormItem label="名称" for="record-name" prop="name" required>
        <SInput id="record-name" v-model="draft.name" required />
      </SFormItem>
      <SFormItem label="启用"><SSwitch v-model="draft.enabled" label="启用" /></SFormItem>
    </SForm>
    <template #footer>
      <SButton @click="editing = false">取消</SButton>
      <SButton variant="primary" type="submit" form="record-form" :loading="busy">保存</SButton>
    </template>
  </SDialog>
</template>
```

## 组件接口

| 组件 | 属性 | 事件 / 插槽 |
| --- | --- | --- |
| `SButton` | `variant=default/primary/danger/text`、`size=small/default`、`loading`、`disabled`、`icon`；原生 `type`、`form` 等透传 | 原生点击；默认插槽可读取 loading |
| `SInput` | `v-model`、`.number`、`.trim`；原生输入属性透传 | `input(Event)`、`change(Event)`；暴露 focus/select/element |
| `STextarea` | `v-model`、`autosize`；原生 rows/maxlength 等 | `input(Event)`；暴露 focus/element |
| `SSelect` | `v-model`、`options=[{value,label,disabled,group}]`、`filterable`、`placeholder` | `change(Event)`；可直接传入 option 插槽；暴露 focus/element |
| `SCheckbox` | `v-model` 为布尔值或字符串数组、`value`、`checked`、`indeterminate` | `change(Event)`；暴露 focus/element |
| `SSwitch` | 布尔 `v-model`、`loading`、`disabled`、`label` | `change(boolean)` |
| `SCard` | `title`、`loading`、`divided` | header / actions / 默认插槽 |
| `SForm` | `model`、`rules`、`disabled` | 校验成功后触发 submit；暴露 validate/resetValidation/element |
| `SFormItem` | `label`、`for`、`prop`、`error`、`required` | label / 默认插槽；显示表单校验错误 |
| `SPageHeader` | `title`、`count` | 默认插槽为右侧操作 |
| `STabs` | 字符串 `v-model`、`items=[{value,label,count,disabled}]` | `change(string)`；默认插槽提供 active |
| `STable` | `rows`、`columns=[{key,label,sortable}]`、`rowKey=id`、`loading`、`emptyText` | row / cell-字段名 插槽；sort-change；也支持直接放 thead/tbody |
| `SDialog` | `open`、`title`、`wide` | close；默认 / footer 插槽 |
| `STag` | `status`、`label` | 状态标签 |
| `SEmpty` | `label`、`icon` | 默认插槽为操作 |

`SDialog`、`STag`、`SEmpty` 与旧名 `UiModal`、`UiBadge`、`UiEmpty` 共用实现，插件无需立即改名。表格、卡片和按钮可暂时保留原有样式类。

`SForm` 的规则格式为 `{required?, min?, validate?(value): boolean, message}`，按字段关联到 `SFormItem prop`。提交同时调用原生表单有效性校验。`validate()` 返回布尔值；所有异步请求和保存状态由业务层管理，组件不触发网络请求。

按钮保留原生 type 语义：表单内不负责提交的操作应显式 `type="button"`。弹窗 footer 中用 `form="表单ID" type="submit"` 提交指定表单。

## 标签和表格

```vue
<STabs v-model="tab" :items="[
  {value:'records',label:'记录',count:rows.length},
  {value:'settings',label:'设置'}
]">
  <Transition name="s-page" mode="out-in">
    <div :key="tab">
      <STable v-if="tab==='records'" :rows="rows" :columns="[
        {key:'name',label:'名称',sortable:true},
        {key:'enabled',label:'状态'}
      ]">
        <template #cell-enabled="{row}"><STag :status="row.enabled?'enabled':'disabled'" /></template>
      </STable>
    </div>
  </Transition>
</STabs>
```

表格排序在当前传入 rows 内执行，不负责远端分页。标签支持方向键和 Home / End，滑动指示器随容器尺寸和内容变化更新。选择框使用自绘触发器和 Popover 弹层，支持方向键、回车、Esc、Home / End、键入定位、禁用项及分组。条目超过 8 个或设置 filterable 时显示搜索框。弹层自动选择向上或向下展开，使用浏览器顶层展示，避免被表格、弹窗或滚动容器裁剪。内部隐藏的原生 select 仅用于表单有效性校验和兼容 change(Event)，不会展示系统下拉菜单。多选使用 SCheckbox 数组模型。

## 动效与约定

组件统一使用 `--accent`、`--border`、`--ink` 等主题变量；`--s-radius`、`--s-motion`、`--s-spring` 控制圆角和时序。动效包括按钮按压、开关滑块、复选标记、标签指示器、表单错误、遮罩、弹窗和页面切换。系统开启减少动态效果时自动缩减动画。

弹窗只允许显式关闭，不因遮罩点击或 Esc 丢失编辑内容。页面保留标题、字段、状态和操作；不放入产品描述、解释段落或声明。模型返回内容、人格提示词和用户填写的业务描述属于业务数据。
