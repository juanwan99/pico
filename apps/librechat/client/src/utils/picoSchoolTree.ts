import {
  listEduFields,
  searchEduSchoolMaterials,
  type EduSchoolField,
  type EduSchoolMaterial,
} from '~/data-provider/pico/api';

export type SchoolFieldGroup = {
  field: EduSchoolField;
  items: EduSchoolMaterial[];
};

function materialFieldId(row: EduSchoolMaterial) {
  return typeof row.fieldId === 'string' && row.fieldId ? row.fieldId : '';
}

function tagItems(items: EduSchoolMaterial[], fallbackFieldId = '') {
  return items.map((item) => ({
    ...item,
    fieldId: materialFieldId(item) || fallbackFieldId || undefined,
  }));
}

/** Fields only — first paint for the venue folder tree. */
export async function loadSchoolFields(): Promise<{
  fields: EduSchoolField[];
  configured?: boolean;
}> {
  const fieldsRow = await listEduFields().catch(() => ({
    fields: [] as EduSchoolField[],
    configured: undefined as boolean | undefined,
  }));
  return {
    fields: Array.isArray(fieldsRow.fields) ? fieldsRow.fields : [],
    configured: fieldsRow.configured,
  };
}

/** One venue's documents (lazy expand). */
export async function loadSchoolFieldItems(fieldId: string): Promise<{
  items: EduSchoolMaterial[];
  configured?: boolean;
}> {
  const id = String(fieldId || '').trim();
  if (!id || id === 'other') {
    return { items: [], configured: true };
  }
  try {
    const row = await searchEduSchoolMaterials('', id);
    const items = Array.isArray(row.items) ? row.items : [];
    return { items: tagItems(items, id), configured: row.configured };
  } catch {
    return { items: [], configured: true };
  }
}

/**
 * Venue tree without N+1 fan-out.
 * Parallel: fields list + one unscoped materials search, then group by fieldId.
 * Empty venues still appear from the fields list.
 */
export async function loadSchoolFieldTree(): Promise<{
  fields: EduSchoolField[];
  items: EduSchoolMaterial[];
  configured?: boolean;
}> {
  const [fieldsRow, materialsRow] = await Promise.all([
    loadSchoolFields(),
    searchEduSchoolMaterials('', '').catch(() => ({
      items: [] as EduSchoolMaterial[],
      configured: undefined as boolean | undefined,
    })),
  ]);
  const fields = fieldsRow.fields;
  const items = tagItems(Array.isArray(materialsRow.items) ? materialsRow.items : []);
  const configured =
    fieldsRow.configured === false || materialsRow.configured === false
      ? false
      : fieldsRow.configured ?? materialsRow.configured;
  return { fields, items, configured };
}

export function groupSchoolTree(
  fields: EduSchoolField[],
  items: EduSchoolMaterial[],
): SchoolFieldGroup[] {
  const byField = new Map<string, SchoolFieldGroup>();
  for (const field of fields) {
    if (!field.id) continue;
    byField.set(field.id, { field, items: [] });
  }
  const other: EduSchoolMaterial[] = [];
  for (const item of items) {
    if (!item.id) continue;
    const fid = materialFieldId(item);
    const bucket = fid ? byField.get(fid) : undefined;
    if (bucket) {
      bucket.items.push(item);
    } else {
      other.push(item);
    }
  }
  const listed = [...byField.values()];
  if (other.length) {
    listed.push({ field: { id: 'other', name: '其他' }, items: other });
  }
  return listed;
}
