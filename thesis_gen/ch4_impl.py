# -*- coding: utf-8 -*-
"""Chapter 4: System Implementation Details"""

def get_ch4():
    return r"""# فصل چهارم: پیاده‌سازی سیستم

این فصل به تشریح دقیق جزئیات پیاده‌سازی نرم‌افزاری مؤلفه‌های سامانه TrainSwarm، ساختار فایل‌ها، کلاس‌ها، الگوریتم‌های اجرایی و مکانیزم‌های مدیریت خطا می‌پردازد.

---

## ۴-۱. محیط پیاده‌سازی و ابزارهای توسعه

### ۴-۱-۱. زبان‌ها و چارچوب‌های توسعه
سامانه TrainSwarm از یک معماری چندزبانه (Polyglot) بهره می‌گیرد که در آن هر بخش با مناسب‌ترین ابزار مهندسی متناسب با نیازمندی‌هایش پیاده‌سازی شده است:
- **C# .NET 10 (Coordinator):** انتخاب شده برای لایه هماهنگی به دلیل توان عملیاتی ناهمگام استثنایی سرور وب Kestrel، کارایی حافظه، پشتیبانی پیشرفته از تراکنش‌های دیتابیس با Entity Framework Core و سازگاری استاندارد با استریم‌های دوطرفه gRPC HTTP/2.
- **Go 1.22 (P2P Sidecars & Relay):** انتخاب شده برای لایه انتقال شبکه به دلیل کامپایل ایستا، اجرای سبک Goroutineها جهت مدیریت همزمان سوکت‌ها، مصرف رم ناچیز (کمتر از ۳۰ مگابایت) و پشتیبانی رسمی و پایدار از کتابخانه libp2p.
- **Python 3.11+ (Client & Trainer Data Plane):** انتخاب شده برای خطوط لوله یادگیری ماشین به دلیل برخورداری از اکوسیستم بی‌رقیب PyTorch 2.2+، Hugging Face Transformers 4.40+، Accelerate و کتابخانه SafeTensors 0.4+.

### ۴-۱-۲. ساختار پروژه و جداسازی مسئولیت‌ها
معماری پروژه بر اساس اصل جداسازی دغدغه‌ها (Separation of Concerns) و معماری تمیز (Clean Architecture) پایه‌ریزی شده است:

```
TrainSwarm/
├── src/
│   ├── Coordinator/                     # لایه هماهنگی (.NET 10)
│   │   ├── TrainSwarm.Coordinator.Domain/          # موجودیت‌های کسب‌وکار (Trainer, TrainingTask)
│   │   ├── TrainSwarm.Coordinator.Application/     # سرویس‌ها و زمان‌بند (SchedulerService)
│   │   ├── TrainSwarm.Coordinator.Infrastructure/  # ماندگاری با EF Core و SQLite
│   │   └── TrainSwarm.Coordinator.Api/             # کنترلرهای REST و سرور استریم gRPC
│   ├── bootstrap-relay/                 # سرور رله شبکه (Go 1.22 libp2p)
│   ├── p2p-node/                        # فرآیند جانبی P2P (Go 1.22 sidecar)
│   ├── distributed_training_engine/     # موتور انتزاعی آموزش (Python)
│   │   ├── adapters/                    # آداپتورهای مدل (CCDM و Torch)
│   │   ├── partitioning/                # شاردبندی دیتاست
│   │   ├── training/                    # ارکستراسیون آموزش
│   │   └── aggregation/                 # تجمیع فدرال
│   ├── Client/                          # برنامه کلاینت مدیریت آموزش (Python)
│   └── Trainer/                         # عامل پردازشی آموزش (Python)
```

این تفکیک تضمین می‌کند که تغییر در لایه شبکه (مثلاً ارتقای پروتکل‌های libp2p) یا تغییر در لایه ذخیره‌سازی، کوچکترین اثری بر کد حلقه آموزش PyTorch یا الگوریتم زمان‌بندی هماهنگ‌کننده نخواهد گذاشت.

### ۴-۱-۳. اجرای چند گره و محیط استقرار آزمایش
سامانه برای پشتیبانی از دو سناریوی استقرار طراحی شده است:
۱. **سناریوی کانتینری Docker (`samples/full_distributed_training_test`):** استقرار در قالب چندین شبکه Bridge مجزا برای شبیه‌سازی دقیق فایروال‌های محلی NAT.
۲. **سناریوی بومی پردازه‌های مجزا (`samples/canonical_causal_decoder_training_test`):** اجرای مؤلفه‌ها به عنوان پردازه‌های مستقل سیستم‌عامل با پورت‌ها و دایرکتوری‌های کاری مجزا بر روی یک یا چند ماشین فیزیکی:
- **Bootstrap Relay:** پورت TCP/UDP 4001 و HTTP 8090.
- **Coordinator:** پورت REST 8080 و پورت gRPC 8081.
- **Client Node:** فرآیند جانبی P2P روی پورت 9001 و رابط محلی gRPC روی 50051.
- **Trainer 1:** فرآیند جانبی P2P روی پورت 9002 و رابط محلی gRPC روی 50052.
- **Trainer 2:** فرآیند جانبی P2P روی پورت 9003 و رابط محلی gRPC روی 50053.

---

## ۴-۲. پیاده‌سازی گره کلاینت

### ۴-۲-۱. آماده‌سازی و اعتبارسنجی مدل
کلاینت با دریافت مسیر آرشیو فشرده مدل پایه (`.gz`)، آن را بررسی می‌کند. ماژول کلاینت فاقد وابستگی سخت به یک شبکه عصبی خاص است و از طریق انتزاع مدل‌ها، بسته‌بندی را بررسی می‌کند:
```python
model_dest = model_staging_dir / f"{model_id}_{command.model_version}.gz"
shutil.copy2(command.model_path, model_dest)

config_dest = model_staging_dir / f"{model_id}_{command.model_version}_config.json"
with open(config_dest, "w", encoding="utf-8") as f:
    json.dump(normalized_training_config, f, indent=2)
```

### ۴-۲-۲. آماده‌سازی و اعتبارسنجی دیتاست
ماژول `CanonicalCausalDecoderPartitioner` در زمان بارگذاری فایل دیتاست (`.pt`)، انطباق تانسورها با قرارداد استاندارد را کنترل می‌کند:
```python
REQUIRED_KEYS = ("input_ids", "attention_mask", "labels")

for req_key in REQUIRED_KEYS:
    if req_key not in raw_data:
        raise DatasetFormatError(f"Dataset missing required canonical key '{req_key}'.")
    tensor = raw_data[req_key]
    if not isinstance(tensor, torch.Tensor) or tensor.ndim != 2:
        raise DatasetFormatError(f"Key '{req_key}' must be 2D tensor (batch, seq_len).")
```
همچنین طول توالی و تعداد نمونه‌ها در هر سه تانسور مقایسه می‌شوند تا عدم تطابق ابعادی پیش از شروع کار شناسایی شود.

### ۴-۲-۳. پیاده‌سازی Partitioner و اجرای تست دود (Smoke Test)
فرایند شاردبندی توسط کلاس `SubmitTrainingCommandHandler` و با همکاری `SmokeTestCommandHandler` هدایت می‌شود:
۱. **استخراج نمونه:** تابع `CreateSample()` تعداد ۲ نمونه اول دیتاست را برش زده و به صورت موقت ذخیره می‌سازد.
۲. **سنجش بنچمارک:** کلاس `SmokeTestCommandHandler` یک تسک آزمایشی ساخته و زمان آموزش ($\Delta t_{\text{smoke}}$) را با ساعت یکنواخت پردازنده (`time.perf_counter()`) ثبت می‌کند:
```python
start_time = time.perf_counter()
orchestrator_result = self.training_orchestrator.run(task=smoke_task, working_directory=work_dir)
elapsed_seconds = time.perf_counter() - start_time

throughput = sample_count / elapsed_seconds
estimated_shard_size = max(1, int(throughput * self.shard_training_time_limit))
recommended_shard_size = max(1, int(estimated_shard_size * self.safety_factor))
```
۳. **تولید شاردها:** با اندازه محاسبه‌شده، تابع `CreateShards()` کل داده را در حلقه‌ای پیوسته به تکه‌های بدون همپوشانی تقسیم می‌کند:
```python
while start_idx < total_samples:
    end_idx = min(start_idx + shardSampleSize, total_samples)
    shard_id = f"shard_{shard_seq}"
    shard_dict = {k: v[start_idx:end_idx].detach().clone() for k, v in raw_data.items()}
    torch.save(shard_dict, str(shard_path))
    shards.append(PartitionedShard(shardId=shard_id, sampleCount=end_idx - start_idx, artifactPath=str(shard_path)))
    start_idx = end_idx
    shard_seq += 1
```

### ۴-۲-۴. ثبت تسک و پیگیری شاردها با SQLite
اطلاعات هر شارد در جدول `training_shards` دیتابیس کلاینت ثبت می‌شود:
```sql
CREATE TABLE training_shards (
    id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_type TEXT NOT NULL,
    model_version TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    shard_id TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    sample_count INTEGER NOT NULL,
    status TEXT NOT NULL, -- CREATED, READY, TRAINING, COMPLETED, FAILED
    trainer_node_id TEXT,
    metrics TEXT,
    update_artifact_path TEXT
);
```
پس از ثبت رکوردها با وضعیت `CREATED`، کلاس `CoordinatorAdapter` از طریق درخواست HTTP به آدرس `/api/training-tasks` شناسه‌ها را در هماهنگ‌کننده ثبت کرده و سپس وضعیت شاردها به `READY` تغییر می‌یابد.

### ۴-۲-۵. مدیریت نسخه مدل و اتمیک بودن تغییرات
کلاینت نگارش‌های مدل را در جدول `models` ذخیره می‌کند. برای جلوگیری از خراب شدن چک‌پوینت‌ها در حین فشرده‌سازی، فایل جدید ابتدا با یک نام تصادفی در مسیر موقت تولید شده و سپس با دستور اتمیک سیستم‌عامل به نام نهایی تغییر می‌یابد:
```python
temp_archive = output_dir / f"{model_id}_{new_version}_{uuid.uuid4().hex[:8]}.tmp.gz"
with tarfile.open(str(temp_archive), "w:gz") as tar:
    tar.add(str(temp_model_dir), arcname="model")
    tar.add(str(temp_tokenizer_dir), arcname="tokenizer")

# تغییر نام اتمیک با تضمین سطح هسته سیستم‌عامل
os.replace(str(temp_archive), str(target_file))
```

---

## ۴-۳. پیاده‌سازی هماهنگ‌کننده (Coordinator)

### ۴-۳-۱. مدیریت موجودیت‌های Trainer و TrainingTask در EF Core
در پروژه .NET هماهنگ‌کننده، نگاشت موجودیت‌ها با Fluent API در کلاس `CoordinatorDbContext` صورت می‌پذیرد. تفکیک ماشین حالت ترینر از تسک، امکان ره‌گیری دقیق را فراهم می‌سازد:

```
      ماشین حالت ترینر (Trainer)                 ماشین حالت تسک (TrainingTask)
      
          +---------+                                 +---------+
          | UNCLEAR |                                 | UNASSIGN| (TrainerNodeId="")
          +----+----+                                 +----+----+
               | اتصال/آمادگی                              |
               v                                           | زمان‌بند تسک را
          +---------+                                      | به ترینر واگذار می‌کند
          |  IDLE   | <----+                               v
          +----+----+      |                          +---------+
               | تخصیص     | پایان موفقیت‌آمیز         | ASSIGNED| (TrainerNodeId=ID)
               | تسک       | تسک                           +----+----+
               v           |                               |
          +---------+      |                               | خطای ارسال gRPC
          |  BUSY   +------+                               v
          +----+----+                                 +---------+
               | قطعی اتصال gRPC                      | UNASSIGN| (رول‌بک فوری به صف)
               v                                      +---------+
          +---------+
          | UNCLEAR |
          +---------+
```

### ۴-۳-۲. پیاده‌سازی الگوریتم زمان‌بندی عادلانه (SchedulerService.cs)
سرویس زمان‌بندی هماهنگ‌کننده، وظیفه تخصیص عادلانه کارها را بر عهده دارد. پیاده‌سازی کامل این متد در زبان C#:

```csharp
public async Task<ErrorOr<List<AssignedTaskDto>>> AssignTasksAsync(CancellationToken ct = default)
{
    // ۱. دریافت تمام ترینرهای آماده مرتب‌شده بر اساس شناسه
    var availableTrainers = await _dbContext.Trainers
        .Where(t => t.Status == TrainerStatus.IDLE)
        .OrderBy(t => t.TrainerNodeId)
        .ToListAsync(ct);
    if (availableTrainers.Count == 0) return new List<AssignedTaskDto>();

    // ۲. دریافت تسک‌های واگذارنشده مرتب‌شده بر اساس زمان ثبت (FIFO)
    var unassignedTasks = await _dbContext.TrainingTasks
        .Where(t => string.IsNullOrEmpty(t.TrainerNodeId))
        .OrderBy(t => t.SubmitTime)
        .ThenBy(t => t.TrainingTaskId)
        .ToListAsync(ct);
    if (unassignedTasks.Count == 0) return new List<AssignedTaskDto>();

    // ۳. دسته‌بندی تسک‌ها در صف‌های مستقل به ازای هر ModelId
    var modelQueues = new Dictionary<string, Queue<TrainingTask>>(StringComparer.Ordinal);
    foreach (var task in unassignedTasks)
    {
        if (!modelQueues.TryGetValue(task.ModelId, out var queue))
        {
            queue = new Queue<TrainingTask>();
            modelQueues[task.ModelId] = queue;
        }
        queue.Enqueue(task);
    }
    var activeModelIds = modelQueues.Keys.OrderBy(m => m, StringComparer.Ordinal).ToList();

    // ۴. تعیین موقعیت جاری کرسر جهت چرخش عادلانه میان مدل‌ها
    var currentCursor = _cursorState.GetCurrentCursor();
    int currentIndex = Math.Max(0, activeModelIds.IndexOf(currentCursor));

    var assignedPairs = new List<(TrainingTask Task, Trainer Trainer)>();
    int trainerIndex = 0;

    // ۵. حلقه تخصیص دوره‌ای و متعادل
    while (trainerIndex < availableTrainers.Count && activeModelIds.Count > 0)
    {
        if (currentIndex >= activeModelIds.Count) currentIndex = 0;
        var modelId = activeModelIds[currentIndex];
        var queue = modelQueues[modelId];

        var task = queue.Dequeue();
        var trainer = availableTrainers[trainerIndex];

        task.TrainerNodeId = trainer.TrainerNodeId;
        trainer.Status = TrainerStatus.BUSY;
        assignedPairs.Add((task, trainer));
        trainerIndex++;

        if (queue.Count == 0) activeModelIds.RemoveAt(currentIndex);
        else currentIndex++;
    }

    _cursorState.SetCurrentCursor(activeModelIds.Count > 0 ? activeModelIds[currentIndex % activeModelIds.Count] : string.Empty);
    await _dbContext.SaveChangesAsync(ct);

    // ۶. ارسال بلادرنگ دستور به ترینرها با محافظت رول‌بک
    foreach (var (assignedTask, assignedTrainer) in assignedPairs)
    {
        var command = new StartTrainingCommand {
            ClientNodeId = assignedTask.ClientNodeId,
            ModelId = assignedTask.ModelId,
            ModelVersion = assignedTask.ModelVersion,
            DataSetId = assignedTask.DataSetId,
            ShardId = assignedTask.ShardId
        };

        var dispatchResult = await _commandCenter.SendAsync(assignedTrainer.TrainerNodeId, command);
        if (!dispatchResult.IsSuccess)
        {
            // لغو فوری تخصیص در صورت شکست در ارسال پیام
            assignedTask.TrainerNodeId = string.Empty;
            assignedTrainer.Status = TrainerStatus.UNCLEAR;
            await _dbContext.SaveChangesAsync(ct);
        }
    }
    return assignedResults;
}
```

### ۴-۳-۳. مدیریت چرخه عمر تسک و رویدادهای تغییر وضعیت
تخصیص تسک به معنای موفقیت آموزش نیست. هماهنگ‌کننده صرفاً ثبت می‌کند که تسک به کدام ترینر واگذار شده است. تایید نهایی آموزش تنها زمانی محقق می‌شود که کلاینت فایل دلتای معتبر را دریافت و وضعیت شارد را در پایگاه داده خود به عنوان `COMPLETED` نشانه‌گذاری نماید.

### ۴-۳-۴. ارتباطات ناهمگام استریم gRPC
هماهنگ‌کننده سرویس `CoordinatorCommandService` را روی پورت ۸۰۸۱ فعال می‌سازد. ترینرها متد `SubscribeCommands` را فراخوانی کرده و یک جریان HTTP/2 زنده نگه می‌دارند:
```protobuf
message CommandEnvelope {
  string id = 1;
  string type = 2; // "StartTrainingCommand"
  string data = 3; // JSON محتوای دستور
}
```
هرگاه تسکی تخصیص یابد، هماهنگ‌کننده شیء JSON را در پاکت `CommandEnvelope` بسته‌بندی کرده و در استریم سوکت ترینر می‌نویسد.

---

## ۴-۴. پیاده‌سازی عاملهای آموزش (Trainer Agents)

### ۴-۴-۱. فازهای چهارگانه در آداپتور CCDM
کلاس `CanonicalCausalDecoderTrainer` چرخه حیات آموزش محلی را در چهار فاز مجزا اجرا می‌کند:

#### ۱. فاز اعتبارسنجی (`validate`)
در این مرحله هیچ فایلی باز نگه داشته نمی‌شود و هیچ محاسباتی آغاز نمی‌گردد:
```python
self.config = CanonicalCausalDecoderTrainingConfig.from_dict(self.task.training)
self.config.validate()

# بررسی ساختار داخلی آرشیو بدون استخراج کامل آن روی دیسک
with tarfile.open(str(self.model_archive_path), "r:*") as tar:
    names = tar.getnames()
    has_model = any(n == "model" or n.startswith("model/") for n in names)
    has_tok = any(n == "tokenizer" or n.startswith("tokenizer/") for n in names)
    if not (has_model and has_tok):
        raise ModelContractViolationError("Archive must contain 'model/' and 'tokenizer/'.")
```

#### ۲. فاز آماده‌سازی (`prepare`)
استخراج فایل‌ها، بارگذاری مدل روی حافظه و عکس‌برداری تغییرناپذیر از وزن‌های پایه:
```python
self.model = AutoModelForCausalLM.from_pretrained(str(model_dir)).to(self.device)

# عکس‌برداری انجمادی از پارامترهای پایه روی رم پردازنده اصلی (CPU)
self.baseline_parameters = {
    name: param.detach().clone().cpu()
    for name, param in self.model.named_parameters()
    if param.requires_grad
}
```

#### ۳. فاز آموزش (`train`)
پیکربندی پارامترهای Hugging Face و اجرای حلقه گرادیان:
```python
training_args = TrainingArguments(
    output_dir=str(self.working_directory / "output"),
    per_device_train_batch_size=self.config.batch_size,
    learning_rate=self.config.learning_rate,
    num_train_epochs=self.config.epochs,
    weight_decay=self.config.weight_decay,
    fp16=self.config.fp16 and torch.cuda.is_available(),
    logging_steps=1,
    save_strategy="no",
    report_to=[],
)
self.hf_trainer = Trainer(model=self.model, args=training_args, train_dataset=hf_dataset)
train_output = self.hf_trainer.train()
```

#### ۴. فاز ذخیره‌سازی نتیجه و تولید تفاضل (`save_result`)
استخراج وزن‌های به‌روزرسانی‌شده، اعتبارسنجی ابعادی و ذخیره با SafeTensors:
```python
delta_dict = {}
for name, base_tensor in self.baseline_parameters.items():
    trained_tensor = trained_parameters[name]
    if trained_tensor.shape != base_tensor.shape:
        raise TensorCompatibilityError(f"Shape mismatch for '{name}'")
    # محاسبه تفاضل محلی: trained - base
    delta_dict[name] = (trained_tensor - base_tensor).contiguous()

save_file(delta_dict, str(delta_path))
```

---

## ۴-۵. پیاده‌سازی Aggregator و تجمیع نتایج

کلاس `CanonicalCausalDecoderAggregator` وظیفه تجمیع نتایج در سمت کلاینت را بر عهده دارد:

### ۴-۵-۱. بارگذاری و اعتبارسنجی تفاضل‌ها
پیش از شروع تجمیع، فایل‌های SafeTensors بازخوانی شده و کلیدها و ابعاد تانسورها با ساختار پارامترهای مدل پایه مقایسه می‌گردند. اگر نام پارامتری در مدل وجود نداشته باشد یا بعد تانسور ناهماهنگ باشد، کل فرایند با پرتاب استثنای `TensorCompatibilityError` متوقف می‌شود.

### ۴-۵-۲. محاسبه میانگین‌گیری وزندار نمونه‌ای FedAvg
جهت پیشگیری از افت دقت عددی ناشی از تفاوت ممیزهای شناور، محاسبات تجمیع در دقت `float32` انجام می‌گیرد:
```python
total_samples = sum(u.samples_trained for u, _ in self.loaded_deltas)
first_delta = self.loaded_deltas[0][1]

# مقداردهی اولیه تانسور انباشتگر با صفر
aggregated = {
    name: torch.zeros_like(tensor, dtype=torch.float32)
    for name, tensor in first_delta.items()
}

# اعمال ترکیب خطی وزن‌دار
for update, delta_dict in self.loaded_deltas:
    weight = float(update.samples_trained) / float(total_samples)
    for name, delta_tensor in delta_dict.items():
        aggregated[name].add_(delta_tensor.to(torch.float32), alpha=weight)

# بازگردانی به نوع اولیه پارامترها (مثلا float16 یا float32)
self.aggregated_delta = {
    name: tensor.to(first_delta[name].dtype).contiguous()
    for name, tensor in aggregated.items()
}
```

### ۴-۵-۳. تولید نسخه جدید مدل
در متد `CreateNewVersion()`، تفاضل تجمیع‌شده به وزن‌های مدل پایه اضافه می‌شود:
$$W_{\text{new}}[p] = W_{\text{base}}[p] + \Delta W_{\text{aggregated}}[p]$$
وزن‌های جدید در پوشه موقت ذخیره شده، فایل‌های توکنایزر بدون دستکاری کپی می‌شوند، پوشه به صورت یک فایل tar فشرده با فرمت `.gz` بسته‌بندی شده و در نهایت با دستور اتمیک جایگزین نام نهایی می‌گردد.

---

## ۴-۶. پیاده‌سازی فرآیندهای جانبی Go و لایه انتقال P2P

یکی از تمایزهای فنی برجسته TrainSwarm، واگذاری مسئولیت‌های شبکه همتابه‌همتا به یک برنامه کامپایل‌شده مستقل در زبان Go (`src/p2p-node`) است.

### ۴-۶-۱. مدیریت اسلات رله و تازه‌سازی خودکار مجوز در Go
تابع `ReserveRelaySlot` در فرآیند جانبی، وظیفه اتصال به سرور رله و برقراری ارتباط پایدار را بر عهده دارد:
```go
func ReserveRelaySlot(ctx context.Context, h host.Host, relayAddr string) (peer.ID, error) {
    ma, err := multiaddr.NewMultiaddr(relayAddr)
    if err != nil { return "", err }

    relayInfo, err := peer.AddrInfoFromP2pAddr(ma)
    if err != nil { return "", err }

    if err := h.Connect(ctx, *relayInfo); err != nil {
        return "", fmt.Errorf("failed to connect to relay: %w", err)
    }

    reservation, err := client.Reserve(ctx, h, *relayInfo)
    if err != nil {
        return "", fmt.Errorf("failed to reserve slot on relay: %w", err)
    }

    // چرخه پس‌زمینه برای تمدید خودکار اجاره اسلات پیش از انقضا
    go func() {
        for {
            select {
            case <-ctx.Done():
                return
            case <-time.After(time.Until(reservation.Expiration) - 1*time.Minute):
                res, err := client.Reserve(ctx, h, *relayInfo)
                if err == nil {
                    reservation = res
                } else {
                    time.Sleep(30 * time.Second)
                }
            }
        }
    }()

    return relayInfo.ID, nil
}
```

### ۴-۶-۲. پیاده‌سازی هندلرهای سیم libp2p
فرآیند جانبی برای هر پروتکل کاربردی، یک هندلر اختصاصی ثبت می‌کند. به عنوان مثال، در پروتکل `/trainswarm/model/1.0.0`، ترینر ابتدا یک بسته درخواست JSON شامل شناسه و نسخه مدل ارسال می‌کند؛ کلاینت فایل را ارزیابی کرده و سپس بایت‌های خام را مستقیماً درون بافر سوکت می‌ریزد:
```go
func (n *Node) handleModelStream(s network.Stream) {
    defer s.Close()
    var req ModelWireReq
    if err := json.NewDecoder(s).Decode(&req); err != nil { return }

    // فراخوانی کلاینت پایتون از طریق استریم محلی gRPC جهت واکشی مسیر فایل
    localPath, err := n.dispatchModelRequestToClient(req.ModelID, req.ModelVersion)
    if err != nil {
        json.NewEncoder(s).Encode(FileWireHeader{Success: false, Error: err.Error()})
        return
    }

    file, _ := os.Open(localPath)
    defer file.Close()
    stat, _ := file.Stat()

    // ارسال هدر و سپس استریم تکه‌تکه بایت‌ها با بافر ۳۲ کیلوبایتی
    json.NewEncoder(s).Encode(FileWireHeader{Success: true, FileName: stat.Name(), FileSize: stat.Size()})
    io.Copy(s, file)
}
```

---

## ۴-۷. لایه‌های واسط کاربری دوگانه و مدیریت تنظیمات

سامانه TrainSwarm برای هر دو مؤلفه Client و Trainer، دو واسط کاربری کاملاً مستقل ارائه می‌دهد که هر دو بر روی هندلرهای کاربردی یکسان سوار شده‌اند:

### ۴-۷-۱. واسط خط فرمان متنی (Headless CLI)
این واسط به عنوان حالت پیش‌فرض برای اجرا در کانتینرهای Docker، سرورهای لینوکسی بدون مانیتور (Headless) و اسکریپت‌های اتوماسیون طراحی شده است:
- در کلاینت: `python main.py submit-training --model-type canonical_causal_decoder ...`
- در ترینر: `python main.py` به عنوان یک دیمن پس‌زمینه که منتظر دستورات هماهنگ‌کننده می‌ماند.

### ۴-۷-۲. واسط کاربری گرافیکی مدرن (PyQt6 Reactive Desktop GUI)
برای تسهیل استفاده پژوهشگران و کاربران مستقل، یک واسط گرافیکی تعاملی پیاده‌سازی شده است (`python main.py gui`):
- **معماری عدم انجماد واسط (Non-blocking GUI):** کلیه فرایندها نظیر دانلود شارد، استریم مدل و حلقه آموزش پایتورچ در رشته‌های پس‌زمینه (`QThread`) اجرا می‌شوند و از طریق سیستم Signal/Slot وضعیت پیشرفت و نمودارهای لحظه‌ای را به نخ اصلی گرافیک مخابره می‌کنند.
- **داشبورد ترینر:** نمایش لحظه‌ای استپ‌های آموزش، مصرف حافظه کارت گرافیک، نمودار تغییرات لحظه‌ای تابع خطا (Dynamic Loss Chart) و وضعیت اتصال به رله و هماهنگ‌کننده.

### ۴-۷-۳. مدیریت متمرکز پیکربندی و تزریق وابستگی (Dependency Injection)
جهت جلوگیری از وابستگی مستقیم کدها به فراخوانی‌های پراکنده `os.environ`، ماژول‌های `ConfigManager` تمام متغیرهای محیطی (`COORDINATOR_URL`, `BOOTSTRAP_RELAY_ADDR`, `WORKING_DIR`) را در زمان بارگذاری اعتبارسنجی کرده و در قالب اشیای تغییرناپذیر به کانتینر تزریق وابستگی (`Container`) تحویل می‌دهند. این الگو ضامن قابلیت آزمون‌پذیری بالا (Testability) و عایق‌بندی خطاهاست.

---

## ۴-۸. مدیریت استثناها و خطاها در سطح MVP

در یک سامانه توزیع‌شده ناهمگون، وقوع خطا اجتناب‌ناپذیر است. تدابیر اتخاذشده در سطح پیش‌نمونه TrainSwarm عبارتند از:

۱. **قطع ناگهانی ارتباط عامل (Worker Disconnection):**  
اگر در حین ارسال دستور gRPC ارتباط قطع شود، متد `ICommandCenter.SendAsync` با خطا بازگشته و زمان‌بند بلافاصله وضعیت تسک را به حالت بدون تخصیص (`TrainerNodeId = string.Empty`) برگردانده و وضعیت عامل را `UNCLEAR` می‌کند تا تسک برای گره دیگری زمان‌بندی شود.

۲. **خطاهای درون آموزش محلی (CUDA OOM / Dataset Corruption):**  
در صورتی که عامل در حین آموزش با خطای کمبود حافظه مواجه شود، بلاک `try...except` در کلاس `StartTrainingHandler` خطا را شکار کرده، وضعیت ترینر را به `FAILED` تغییر می‌دهد و با لاگ کردن خطا، از ارسال یک فایل ناقص به کلاینت جلوگیری می‌کند.

۳. **خروجی ناقص یا ناهماهنگ (Malformed Artifacts):**  
کلاینت در مرحله `ValidateDelta()`، ساختار هدر و هش تانسورها را ارزیابی می‌کند. هرگونه فایلی که فاقد امضای معتبر SafeTensors باشد، توسط کلاینت طرد شده و وارد حلقه تجمیع نمی‌گردد.

۴. **تکرار تسک و رفتار پایدار (Idempotency):**  
شناسه‌های تسک‌ها از نوع Guid بوده و هر شارد دارای شناسه متنی ثابت است. اگر کلاینت به دلیل تأخیر شبکه، برای یک شارد قبلاً دلتا ثبت کرده باشد، با مکانیزم کنترل نسخه از ورود چندباره دلتا به یک دور جلوگیری به عمل می‌آید.
"""
