This repository is a fork of the original **Arma 3 Object Builder** project by [**MrClock8163**](https://github.com/MrClock8163/Arma3ObjectBuilder). It contains additional fixes and improvements focused primarily on P3D workflows, model import and export, proxy handling, material previews and validation. The original project and its history are preserved, while changes specific to this fork are maintained separately.

## Fork Improvements
### Improved P3D Import
- Improved P3D handling when importing via **drag and drop**.
- Added a `Load Textures` option when importing P3D files.
- P3D texture references are automatically used to create Blender material previews, including texture-based and color materials.
- Missing textures no longer interrupt the import process and are reported in the import log.

### Batch Proxy Extraction
- `Extract Proxy` now supports extracting multiple selected proxies in a single operation.

### Improved P3D Export Process
Model preparation and export validation have been improved:
- Fire Geometry and View Geometry can now contain proxies without causing validation or export errors.
- Unnecessary materials are removed from Geometry, View Geometry, Shadow and Memory LODs before export.
- `Component##` selections are automatically regenerated for geometry-type LODs, including Geometry, View Geometry and Fire Geometry.
- Existing `Occluder##` selections and proxies are not affected by `Component##` generation.
- Export is cancelled if a required validation check fails, with the specific reason reported to the user.

### Geometry Validation
- Added strict Geometry validation for unused vertices and mass assigned to each physical component.
- Missing mass or unused vertices prevent export.

### Fire Geometry Validation
- Added strict validation of Fire Geometry materials on every used face.
- Every Fire Geometry material must reference a valid **penetration RVMAT** from the `P:\DZ\data\data\penetration\` directory.
- Faces with missing or invalid penetration materials prevent export.

### Roadway Validation
- Added strict validation of Roadway sound textures: every face must have a sound texture assigned, and the referenced file must exist.
- RVMAT files cannot be used as Roadway sound textures.
- Missing or invalid sound textures prevent export.

### Additional Improvements
- Improved proxy handling during P3D import and export.
- Improved validation of data before export.
- Improved export error reporting.


## License
As inherited from the **ArmAToolbox**, the **Arma 3 Object Builder** add-on is released under the GNU General Public License version 3. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR  PARTICULAR PURPOSE. See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program. If not, see the [GNU licenses](http://www.gnu.org/licenses/). Files created using this software are not covered by this license.

# RU
Этот репозиторий является форком оригинального проекта **Arma 3 Object Builder** от [**MrClock8163**](https://github.com/MrClock8163/Arma3ObjectBuilder). Форк содержит дополнительные исправления и улучшения, направленные в первую очередь на работу с P3D, импорт и экспорт моделей, обработку proxy, предпросмотр материалов и валидацию данных. Оригинальный проект и его история сохраняются, а изменения, относящиеся к этому форку, поддерживаются отдельно.

## Изменения в этом форке
### Улучшен импорт P3D
- Исправлена обработка P3D при импорте через **drag and drop**.
- Добавлена опция `Load Textures` при импорте P3D.
- Референсные текстуры P3D автоматически используются для создания предпросмотра материалов Blender, включая текстурные и цветовые материалы.
- Отсутствующие текстуры не прерывают импорт и отображаются в логе импорта.

### Извлечение нескольких Proxy
- `Extract Proxy` теперь позволяет извлекать несколько выделенных proxy одновременно.

### Улучшен процесс экспорта P3D
Улучшены подготовка моделей и система валидации перед экспортом:
- Fire Geometry и View Geometry теперь могут содержать proxy без ошибок валидации и экспорта.
- Перед экспортом удаляются ненужные материалы из Geometry, View Geometry, Shadow и Memory LOD.
- При экспорте автоматически пересоздаются `Component##` для geometry-type LOD, включая Geometry, View Geometry и Fire Geometry.
- При генерации `Component##` существующие `Occluder##` и proxy не затрагиваются.
- При провале обязательных проверок экспорт прекращается, а пользователю отображается конкретная причина ошибки.

### Валидация Geometry
- Добавлена строгая проверка Geometry на наличие неиспользуемых вершин и массы у каждого физического компонента.
- Отсутствующая масса или наличие неиспользуемых вершин блокируют экспорт.

### Валидация Fire Geometry
- Добавлена строгая проверка материалов Fire Geometry у каждой используемой грани.
- Каждый используемый материал Fire Geometry должен ссылаться на корректный **penetration RVMAT** из директории `P:\DZ\data\data\penetration\`.
- Грани с отсутствующим или некорректным penetration material блокируют экспорт.

### Валидация Roadway
- Добавлена строгая проверка sound texture у граней Roadway: у каждой грани должна быть указана sound texture, а сам файл должен существовать.
- RVMAT нельзя использовать в качестве sound texture для Roadway.
- Отсутствующая или некорректная sound texture блокирует экспорт.

### Дополнительные улучшения
- Улучшена обработка proxy при импорте и экспорте P3D.
- Улучшена валидация данных перед экспортом.
- Улучшены сообщения об ошибках при экспорте.

## Лицензия
Как и унаследованный от ArmAToolbox проект, Arma 3 Object Builder распространяется под лицензией GNU General Public License версии 3 (GPLv3). Программа распространяется в надежде, что она будет полезна, но БЕЗ КАКИХ-ЛИБО ГАРАНТИЙ, включая, помимо прочего, гарантии товарной пригодности или пригодности для определённой цели. Подробности см. в тексте GNU General Public License. Копия GNU General Public License должна поставляться вместе с программой. Если её нет, см.  [GNU licenses](http://www.gnu.org/licenses/). Файлы, созданные с помощью этого программного обеспечения, не подпадают под действие этой лицензии.
