<script setup lang="ts">
import {
  ref,
  reactive,
  computed,
  onMounted,
  usePluginHost,
  formatDate,
  ApiError,
  UiIcon,
  UiModal,
  UiEmpty,
} from "@sakubot/ui";
interface Entry {
  name: string;
  path: string;
  type: "file" | "directory" | "link";
  size: number;
  modified: number;
  version: string;
}
interface Document extends Entry {
  content: string;
  editable: boolean;
  binary: boolean;
}
interface Listing {
  path: string;
  items: Entry[];
  total: number;
  has_more: boolean;
}
const host = usePluginHost();
const rows = ref<Entry[]>([]),
  cwd = ref("."),
  query = ref(""),
  offset = ref(0),
  total = ref(0);
const loading = ref(false),
  busy = ref(false),
  error = ref("");
const uploadInput = ref<HTMLInputElement>();
const editorOpen = ref(false),
  newFile = ref(false),
  editorError = ref("");
const editor = reactive({ path: "", content: "", version: "", editable: true });
const folderOpen = ref(false),
  folderPath = ref("");
const moving = ref<Entry | null>(null),
  destination = ref("");
const deleting = ref<Entry | null>(null),
  recursive = ref(false);
const replacing = ref<{ file: File; path: string; version: string } | null>(
  null,
);
let sequence = 0;
const crumbs = computed(() =>
  cwd.value === "."
    ? []
    : cwd.value
        .split("/")
        .map((name, index, parts) => ({
          name,
          path: parts.slice(0, index + 1).join("/"),
        })),
);
const join = (name: string) =>
  cwd.value === "." ? name : cwd.value + "/" + name;
const size = (bytes: number) =>
  bytes < 1024
    ? bytes + " B"
    : bytes < 1048576
      ? (bytes / 1024).toFixed(1) + " KiB"
      : (bytes / 1048576).toFixed(1) + " MiB";
function failure(exc: unknown) {
  return exc instanceof ApiError && exc.status === 409
    ? "文件已变化，请重新读取后重试"
    : "操作失败";
}
async function load() {
  const current = ++sequence;
  loading.value = true;
  try {
    const q = new URLSearchParams({
      path: cwd.value,
      query: query.value,
      offset: String(offset.value),
    });
    const data = await host.api<Listing>("files?" + q);
    if (current === sequence) {
      rows.value = data.items;
      cwd.value = data.path;
      total.value = data.total;
      error.value = "";
    }
  } catch {
    if (current === sequence) error.value = "加载失败";
  } finally {
    if (current === sequence) loading.value = false;
  }
}
function navigate(path: string) {
  cwd.value = path;
  offset.value = 0;
  query.value = "";
  void load();
}
function search() {
  offset.value = 0;
  void load();
}
function createFile() {
  newFile.value = true;
  Object.assign(editor, {
    path: join(""),
    content: "",
    version: "",
    editable: true,
  });
  editorError.value = "";
  editorOpen.value = true;
}
async function open(row: Entry) {
  if (row.type === "directory") {
    navigate(row.path);
    return;
  }
  if (row.type !== "file") return;
  newFile.value = false;
  editorError.value = "";
  try {
    const data = await host.api<Document>(
      "file?path=" + encodeURIComponent(row.path),
    );
    Object.assign(editor, {
      path: data.path,
      content: data.content,
      version: data.version,
      editable: data.editable,
    });
    editorOpen.value = true;
  } catch (exc) {
    error.value = failure(exc);
  }
}
async function reloadFile() {
  try {
    const data = await host.api<Document>(
      "file?path=" + encodeURIComponent(editor.path),
    );
    Object.assign(editor, {
      content: data.content,
      version: data.version,
      editable: data.editable,
    });
    editorError.value = "";
  } catch (exc) {
    editorError.value = failure(exc);
  }
}
async function save() {
  busy.value = true;
  editorError.value = "";
  try {
    await host.api("file", {
      path: editor.path,
      content: editor.content,
      version: editor.version,
    });
    editorOpen.value = false;
    await load();
    host.toast("已保存");
  } catch (exc) {
    editorError.value = failure(exc);
  } finally {
    busy.value = false;
  }
}
function createFolder() {
  folderPath.value = join("");
  error.value = "";
  folderOpen.value = true;
}
async function mkdir() {
  busy.value = true;
  try {
    await host.api("mkdir", { path: folderPath.value });
    folderOpen.value = false;
    await load();
  } catch (exc) {
    error.value = failure(exc);
  } finally {
    busy.value = false;
  }
}
function move(row: Entry) {
  moving.value = row;
  destination.value = row.path;
  error.value = "";
}
async function saveMove() {
  if (!moving.value) return;
  busy.value = true;
  try {
    await host.api("move", {
      path: moving.value.path,
      destination: destination.value,
      version: moving.value.version,
    });
    moving.value = null;
    await load();
  } catch (exc) {
    error.value = failure(exc);
  } finally {
    busy.value = false;
  }
}
function remove(row: Entry) {
  deleting.value = row;
  recursive.value = false;
  error.value = "";
}
async function confirmRemove() {
  if (!deleting.value) return;
  busy.value = true;
  try {
    await host.api("remove", {
      path: deleting.value.path,
      version: deleting.value.version,
      recursive: recursive.value,
    });
    deleting.value = null;
    await load();
  } catch (exc) {
    error.value = failure(exc);
  } finally {
    busy.value = false;
  }
}
async function download(path: string) {
  try {
    await host.download(
      "download?path=" + encodeURIComponent(path),
      path.split("/").pop() || "download",
    );
  } catch (exc) {
    error.value = failure(exc);
  }
}
async function upload(file: File, path: string, version = "") {
  return host.upload("upload?" + new URLSearchParams({ path, version }), file);
}
async function selectedUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  if (file.size > 20 * 1024 * 1024) {
    error.value = "文件超过 20 MiB";
    return;
  }
  const path = join(file.name);
  busy.value = true;
  error.value = "";
  try {
    await upload(file, path);
    await load();
    host.toast("已上传");
  } catch (exc) {
    if (exc instanceof ApiError && exc.status === 409) {
      try {
        const current = await host.api<Document>(
          "file?path=" + encodeURIComponent(path),
        );
        replacing.value = { file, path, version: current.version };
      } catch (inner) {
        error.value = failure(inner);
      }
    } else error.value = failure(exc);
  } finally {
    busy.value = false;
  }
}
async function confirmUpload() {
  if (!replacing.value) return;
  busy.value = true;
  try {
    await upload(
      replacing.value.file,
      replacing.value.path,
      replacing.value.version,
    );
    replacing.value = null;
    await load();
    host.toast("已上传");
  } catch (exc) {
    error.value = failure(exc);
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>
<template>
  <SPageHeader title="工作空间" :count="total"
    ><SButton icon="folder" @click="createFolder">新建目录</SButton
    ><SButton icon="file" @click="createFile">新建文件</SButton
    ><SButton icon="upload" :loading="busy" @click="uploadInput?.click()"
      >上传</SButton
    ><input ref="uploadInput" type="file" hidden @change="selectedUpload"
  /></SPageHeader>
  <div class="page-toolbar">
    <nav class="file-breadcrumbs" aria-label="目录">
      <SButton variant="text" @click="navigate('.')">工作空间</SButton
      ><template v-for="crumb in crumbs" :key="crumb.path"
        ><UiIcon name="right" :size="12" /><SButton
          variant="text"
          @click="navigate(crumb.path)"
          >{{ crumb.name }}</SButton
        ></template
      >
    </nav>
    <form class="file-search" @submit.prevent="search">
      <SInput
        v-model="query"
        aria-label="搜索文件"
        placeholder="搜索文件"
      /><SButton type="submit" icon="search">搜索</SButton>
    </form>
    <SButton icon="refresh" :loading="loading" @click="load" />
  </div>
  <span
    v-if="error && !folderOpen && !moving && !deleting && !replacing"
    class="form-error"
    role="alert"
    >{{ error }}</span
  >
  <SCard
    ><div class="table-scroll">
      <STable class="file-table"
        ><thead>
          <tr>
            <th>名称</th>
            <th>大小</th>
            <th>修改时间</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.path">
            <td>
              <SButton
                variant="text"
                class="file-name"
                :disabled="row.type === 'link'"
                @click="open(row)"
                ><UiIcon
                  :name="row.type === 'directory' ? 'folder' : 'file'"
                  :size="18"
                /><span>{{ row.name }}</span></SButton
              >
            </td>
            <td class="mono">
              {{ row.type === "file" ? size(row.size) : "—" }}
            </td>
            <td>{{ formatDate(row.modified) }}</td>
            <td>
              <div class="row-actions">
                <SButton
                  v-if="row.type === 'file'"
                  class="icon-button"
                  aria-label="下载"
                  @click="download(row.path)"
                  ><UiIcon name="download" :size="16" /></SButton
                ><SButton
                  class="icon-button"
                  :disabled="row.type === 'link'"
                  aria-label="移动或重命名"
                  @click="move(row)"
                  ><UiIcon name="edit" :size="16" /></SButton
                ><SButton
                  class="icon-button danger-text"
                  :disabled="row.type === 'link'"
                  aria-label="删除"
                  @click="remove(row)"
                  ><UiIcon name="trash" :size="16"
                /></SButton>
              </div>
            </td>
          </tr></tbody
      ></STable>
    </div>
    <UiEmpty v-if="!rows.length" label="暂无文件" icon="folder"
  /></SCard>
  <div class="file-pagination">
    <SButton
      :disabled="offset === 0 || loading"
      @click="
        offset = Math.max(0, offset - 100);
        load();
      "
      >上一页</SButton
    ><span
      >{{ Math.floor(offset / 100) + 1 }} /
      {{ Math.max(1, Math.ceil(total / 100)) }}</span
    ><SButton
      :disabled="offset + 100 >= total || loading"
      @click="
        offset += 100;
        load();
      "
      >下一页</SButton
    >
  </div>
  <UiModal
    :open="editorOpen"
    :title="newFile ? '新建文件' : editor.path"
    wide
    @close="editorOpen = false"
    ><SForm id="workspace-editor" @submit="save"
      ><SFormItem v-if="newFile" label="路径" for="file-path"
        ><SInput
          id="file-path"
          v-model="editor.path"
          required
          maxlength="2048" /></SFormItem
      ><SFormItem v-if="editor.editable" label="内容" for="file-content"
        ><STextarea
          id="file-content"
          v-model="editor.content"
          class="file-editor"
          rows="20"
          maxlength="1048576"
          spellcheck="false" /></SFormItem
      ><span v-else class="badge neutral">仅下载</span
      ><span v-if="editorError" class="form-error" role="alert">{{
        editorError
      }}</span></SForm
    ><template #footer
      ><SButton v-if="!newFile" icon="download" @click="download(editor.path)"
        >下载</SButton
      ><SButton v-if="!newFile" @click="reloadFile">重新读取</SButton
      ><SButton @click="editorOpen = false">关闭</SButton
      ><SButton
        v-if="editor.editable"
        variant="primary"
        type="submit"
        form="workspace-editor"
        :loading="busy"
        >保存</SButton
      ></template
    ></UiModal
  >
  <UiModal :open="folderOpen" title="新建目录" @close="folderOpen = false"
    ><SForm id="workspace-mkdir" @submit="mkdir"
      ><SFormItem label="路径" for="folder-path"
        ><SInput id="folder-path" v-model="folderPath" required /></SFormItem
      ><span v-if="error" class="form-error">{{ error }}</span></SForm
    ><template #footer
      ><SButton @click="folderOpen = false">取消</SButton
      ><SButton
        variant="primary"
        type="submit"
        form="workspace-mkdir"
        :loading="busy"
        >创建</SButton
      ></template
    ></UiModal
  >
  <UiModal :open="!!moving" title="移动或重命名" @close="moving = null"
    ><SForm id="workspace-move" @submit="saveMove"
      ><SFormItem label="目标路径" for="move-path"
        ><SInput id="move-path" v-model="destination" required /></SFormItem
      ><span v-if="error" class="form-error">{{ error }}</span></SForm
    ><template #footer
      ><SButton @click="moving = null">取消</SButton
      ><SButton
        variant="primary"
        type="submit"
        form="workspace-move"
        :loading="busy"
        >保存</SButton
      ></template
    ></UiModal
  >
  <UiModal :open="!!deleting" title="删除" @close="deleting = null"
    ><strong class="mono">{{ deleting?.path }}</strong
    ><label
      v-if="deleting?.type === 'directory'"
      class="checkbox-field recursive-option"
      ><SCheckbox v-model="recursive" />递归删除</label
    ><span v-if="error" class="form-error">{{ error }}</span
    ><template #footer
      ><SButton @click="deleting = null">取消</SButton
      ><SButton variant="danger" :loading="busy" @click="confirmRemove"
        >删除</SButton
      ></template
    ></UiModal
  >
  <UiModal :open="!!replacing" title="覆盖文件" @close="replacing = null"
    ><strong class="mono">{{ replacing?.path }}</strong
    ><span v-if="error" class="form-error">{{ error }}</span
    ><template #footer
      ><SButton @click="replacing = null">取消</SButton
      ><SButton variant="primary" :loading="busy" @click="confirmUpload"
        >覆盖</SButton
      ></template
    ></UiModal
  >
</template>
<style scoped>
.file-breadcrumbs {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex-wrap: wrap;
  flex: 1;
}
.file-search {
  display: flex;
  gap: 8px;
}
.file-search input {
  max-width: 180px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
}
.file-table {
  min-width: 660px;
}
.file-table th:first-child {
  width: 48%;
}
.file-name {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--ink);
  font-weight: 500;
  max-width: 100%;
}
.file-name span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-name svg {
  color: var(--accent);
}
.file-pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
  margin-top: 18px;
  color: var(--muted);
}
.file-editor {
  width: 100%;
  font: 12px/1.8 var(--mono);
  tab-size: 2;
  resize: vertical;
  min-height: 380px;
}
.recursive-option {
  margin-top: 20px;
}
</style>
