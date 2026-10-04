import { useRef } from 'react';
import { emptyProject, removeAt, replaceAt } from '../../lib/profileForm';
import type { ProjectFormValues } from '../../lib/profileForm';
import { fieldDomId } from '../../lib/validationErrors';
import type { FieldErrors } from '../../lib/validationErrors';
import { Button } from '../ui/Button';
import { TextArea } from '../ui/TextArea';
import { TextField } from '../ui/TextField';
import { FormSection } from './FormSection';
import { ListItemFieldset } from './ListItemFieldset';
import { StringListEditor } from './StringListEditor';

const PATH = 'projects';
const MAX_PROJECTS = 20;

interface ProjectsEditorProps {
  projects: readonly ProjectFormValues[];
  errors: FieldErrors;
  onChange: (next: ProjectFormValues[], changedPath: string) => void;
  createItemKey: () => string;
}

/** Projects list: name, description, technologies and an optional link per project. */
export function ProjectsEditor({ projects, errors, onChange, createItemKey }: ProjectsEditorProps) {
  const addButtonRef = useRef<HTMLButtonElement>(null);

  function update(index: number, project: ProjectFormValues, field: string) {
    onChange(replaceAt(projects, index, project), `${PATH}[${String(index)}].${field}`);
  }

  function handleAdd() {
    onChange([...projects, emptyProject(createItemKey())], PATH);
  }

  function handleRemove(index: number) {
    onChange(removeAt(projects, index), PATH);
    addButtonRef.current?.focus();
  }

  return (
    <FormSection
      legend="Projects"
      description="Projects count toward relevance when their technologies match a job."
      errorPath={PATH}
      error={errors[PATH]}
    >
      {projects.length === 0 && <p className="text-sm text-ink-600">No projects yet.</p>}
      {projects.map((project, index) => {
        const path = `${PATH}[${String(index)}]`;
        return (
          <ListItemFieldset
            key={project.key}
            legend={`Project ${String(index + 1)}`}
            path={path}
            error={errors[path]}
            onRemove={() => {
              handleRemove(index);
            }}
          >
            <TextField
              id={fieldDomId(`${path}.name`)}
              label="Project name"
              required
              maxLength={120}
              value={project.name}
              error={errors[`${path}.name`]}
              onChange={(event) => {
                update(index, { ...project, name: event.target.value }, 'name');
              }}
            />
            <TextArea
              id={fieldDomId(`${path}.description`)}
              label="Project description"
              rows={3}
              maxLength={2000}
              value={project.description}
              error={errors[`${path}.description`]}
              onChange={(event) => {
                update(index, { ...project, description: event.target.value }, 'description');
              }}
            />
            <StringListEditor
              legend="Technologies"
              itemLabel="technology"
              path={`${path}.technologies`}
              values={project.technologies}
              errors={errors}
              maxItems={20}
              maxItemLength={50}
              onChange={(technologies, changedPath) => {
                onChange(replaceAt(projects, index, { ...project, technologies }), changedPath);
              }}
            />
            <TextField
              id={fieldDomId(`${path}.url`)}
              label="Project URL"
              type="url"
              hint="Optional. Starts with http:// or https://."
              maxLength={300}
              value={project.url}
              error={errors[`${path}.url`]}
              onChange={(event) => {
                update(index, { ...project, url: event.target.value }, 'url');
              }}
            />
          </ListItemFieldset>
        );
      })}
      <div>
        <Button
          ref={addButtonRef}
          variant="secondary"
          onClick={handleAdd}
          disabled={projects.length >= MAX_PROJECTS}
        >
          Add project
        </Button>
      </div>
    </FormSection>
  );
}
