import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

import '../../../../core/error/app_exception.dart';
import '../../../../core/utils/date_formatter.dart';
import '../models/counsel_session.dart';
import '../models/diary_entry.dart';
import '../models/emotion_report.dart';
import 'diary_data_source.dart';

/// Real diary data: Firestore per FIRESTORE_SCHEMA.md —
/// `users/{uid}/diaries|reports|counsel_sessions/{yyyy-MM-dd}`.
class DiaryRemoteDataSource implements DiaryDataSource {
  DiaryRemoteDataSource({FirebaseAuth? auth, FirebaseFirestore? firestore})
      : _auth = auth ?? FirebaseAuth.instance,
        _firestore = firestore ?? FirebaseFirestore.instance;

  final FirebaseAuth _auth;
  final FirebaseFirestore _firestore;

  String get _uid {
    final uid = _auth.currentUser?.uid;
    if (uid == null) {
      throw const AuthException('로그인이 필요해요. 다시 로그인해주세요.');
    }
    return uid;
  }

  CollectionReference<Map<String, dynamic>> _collection(String name) =>
      _firestore.collection('users').doc(_uid).collection(name);

  @override
  Future<List<DiaryEntry>> fetchEntries() {
    return _guard(() async {
      final snapshot = await _collection('diaries').get();
      return [for (final d in snapshot.docs) DiaryEntry.fromJson(d.data())];
    });
  }

  @override
  Future<DiaryEntry?> fetchEntry(DateTime date) {
    return _guard(() async {
      final doc =
          await _collection('diaries').doc(DateFormatter.dateKey(date)).get();
      final data = doc.data();
      return data != null ? DiaryEntry.fromJson(data) : null;
    });
  }

  @override
  Future<EmotionReport?> fetchReport(DateTime date) {
    return _guard(() async {
      final doc =
          await _collection('reports').doc(DateFormatter.dateKey(date)).get();
      final data = doc.data();
      return data != null ? EmotionReport.fromJson(data) : null;
    });
  }

  @override
  Future<CounselSession?> fetchCounsel(DateTime date) {
    return _guard(() async {
      final doc = await _collection('counsel_sessions')
          .doc(DateFormatter.dateKey(date))
          .get();
      final data = doc.data();
      return data != null ? CounselSession.fromJson(data) : null;
    });
  }

  @override
  Future<Set<DateTime>> fetchRecordedDates() {
    return _guard(() async {
      // Doc ids are the yyyy-MM-dd keys — no field reads needed.
      final snapshot = await _collection('diaries').get();
      final dates = <DateTime>{};
      for (final doc in snapshot.docs) {
        final parsed = DateTime.tryParse(doc.id);
        if (parsed != null) {
          dates.add(DateTime(parsed.year, parsed.month, parsed.day));
        }
      }
      return dates;
    });
  }

  @override
  Future<void> saveRecord({
    required DiaryEntry entry,
    required EmotionReport report,
    required CounselSession counsel,
  }) {
    return _guard(() async {
      final key = DateFormatter.dateKey(entry.date);
      final batch = _firestore.batch()
        ..set(_collection('diaries').doc(key), entry.toJson())
        ..set(_collection('reports').doc(key), report.toJson())
        ..set(_collection('counsel_sessions').doc(key), counsel.toJson());
      await batch.commit();
    });
  }

  /// Maps Firestore exceptions to app-level ones.
  Future<T> _guard<T>(Future<T> Function() run) async {
    try {
      return await run();
    } on FirebaseException catch (e) {
      if (e.code == 'unavailable') {
        throw NetworkException('네트워크 연결이 불안정해요.', e);
      }
      throw ServerException('기록을 처리하지 못했어요. 잠시 후 다시 시도해주세요.', e);
    }
  }
}
