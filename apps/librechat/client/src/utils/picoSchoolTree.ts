import {
  listEduFields,
  searchEduSchoolMaterials,
  type EduSchoolField,
  type EduSchoolMaterial,
} from '~/data-provider/pico/api';

const FIELD_FETCH_CAP = 24;

export type SchoolFieldGroup = {
  field: EduSchoolField;
  items: EduSchoolMaterial[];
};

function materialFieldId(row: EduSchoolMaterial) {
  return typeof row.fieldId === 'string' && row.fieldId ? row.fieldId : '';
}

export async function loadSchoolFieldTree(): Promise<{
  fields: EduSchoolField[];
  items: EduSchoolMaterial[];
  configured?: boolean;
}> {
  const fieldsRow = await listEduFields().catch(() => ({ fields: [] as EduSchoolField[] }));
  const fields = Array.isArray(fieldsRow.fields) ? fieldsRow.fields : [];
  const scoped = fields.filter((field) => field.id).slice(0, FIELD_FETCH_CAP);
  if (scoped.length === 0) {
    const row = await searchEduSchoolMaterials('', '');
    return {
      fields,
      items: Array.isArray(row.items) ? row.items : [],
      configured: row.configured,
    };
  }
  const chunks = await Promise.all(
    scoped.map(async (field) => {
      try {
        const row = await searchEduSchoolMaterials('', field.id);
        const items = Array.isArray(row.items) ? row.items : [];
        return {
          configured: row.configured,
          items: items.map((item) => ({
            ...item,
            fieldId: materialFieldId(item) || field.id,
          })),
        };
      } catch {
        return { configured: true, items: [] as EduSchoolMaterial[] };
      }
    }),
  );
  return {
    fields,
    items: chunks.flatMap((chunk) => chunk.items),
    configured: chunks.every((chunk) => chunk.configured !== false),
  };
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
