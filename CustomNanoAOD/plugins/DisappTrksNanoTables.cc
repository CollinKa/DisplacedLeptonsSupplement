#include <cmath>
#include <map>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include "CondFormats/DataRecord/interface/EcalChannelStatusRcd.h"
#include "CondFormats/EcalObjects/interface/EcalChannelStatus.h"
#include "DataFormats/Common/interface/Handle.h"
#include "DataFormats/DetId/interface/DetId.h"
#include "DataFormats/EcalDetId/interface/EBDetId.h"
#include "DataFormats/EcalDetId/interface/EEDetId.h"
#include "DataFormats/Math/interface/deltaPhi.h"
#include "DataFormats/Math/interface/deltaR.h"
#include "DataFormats/NanoAOD/interface/FlatTable.h"
#include "DataFormats/PatCandidates/interface/Electron.h"
#include "DataFormats/PatCandidates/interface/IsolatedTrack.h"
#include "DataFormats/PatCandidates/interface/Jet.h"
#include "DataFormats/PatCandidates/interface/MET.h"
#include "DataFormats/PatCandidates/interface/Muon.h"
#include "DataFormats/PatCandidates/interface/Tau.h"
#include "DataFormats/PatCandidates/interface/TriggerObjectStandAlone.h"
#include "DataFormats/TrackReco/interface/HitPattern.h"
#include "DataFormats/VertexReco/interface/Vertex.h"
#include "DataFormats/SiPixelDetId/interface/PixelSubdetector.h"
#include "FWCore/Common/interface/TriggerNames.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/Run.h"
#include "FWCore/Framework/interface/stream/EDProducer.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "Geometry/CaloGeometry/interface/CaloCellGeometry.h"
#include "Geometry/CaloGeometry/interface/CaloGeometry.h"
#include "Geometry/CaloGeometry/interface/CaloSubdetectorGeometry.h"
#include "Geometry/Records/interface/CaloGeometryRecord.h"

namespace {
  template <typename T>
  void addColumn(nanoaod::FlatTable &table, const std::string &name, const std::vector<T> &values, const std::string &doc) {
    table.addColumn<T>(name, values, doc);
  }

  std::vector<std::pair<float, float>> triggerObjectEtaPhi(const pat::TriggerObjectStandAloneCollection &triggerObjects,
                                                           const edm::Event &event,
                                                           const edm::TriggerResults &triggerResults,
                                                           const std::string &filterName) {
    std::vector<std::pair<float, float>> out;
    for (auto obj : triggerObjects) {
      obj.unpackNamesAndLabels(event, triggerResults);
      if (obj.hasFilterLabel(filterName)) {
        out.emplace_back(obj.eta(), obj.phi());
      }
    }
    return out;
  }

  template <typename Lepton>
  bool matchedToTriggerObject(const Lepton &lepton, const std::vector<std::pair<float, float>> &triggerObjects, double maxDR) {
    float minDR = 999.f;
    for (const auto &etaPhi : triggerObjects) {
      minDR = std::min(minDR, static_cast<float>(reco::deltaR(lepton.eta(), lepton.phi(), etaPhi.first, etaPhi.second)));
    }
    return minDR < maxDR;
  }

  bool passesTightLepVetoJetId(const pat::Jet &jet) {
    const float absEta = std::abs(jet.eta());
    if (absEta <= 2.6) {
      return jet.neutralHadronEnergyFraction() < 0.99 && jet.neutralEmEnergyFraction() < 0.9 &&
             jet.numberOfDaughters() > 1 && jet.muonEnergyFraction() < 0.8 &&
             jet.chargedHadronEnergyFraction() > 0.01 && jet.chargedMultiplicity() > 0 &&
             jet.chargedEmEnergyFraction() < 0.8;
    }
    if (absEta <= 2.7) {
      return jet.neutralHadronEnergyFraction() < 0.9 && jet.neutralEmEnergyFraction() < 0.99 &&
             jet.muonEnergyFraction() < 0.8 && jet.chargedEmEnergyFraction() < 0.8;
    }
    if (absEta <= 3.0) {
      return jet.neutralHadronEnergyFraction() < 0.99;
    }
    return jet.neutralEmEnergyFraction() < 0.4 && jet.neutralMultiplicity() >= 2;
  }

  float tauIdValue(const pat::Tau &tau, const std::string &label) {
    if (label.empty() || !tau.isTauIDAvailable(label)) {
      return -1.f;
    }
    return tau.tauID(label);
  }

  bool tauPassesId(const pat::Tau &tau,
                   const std::string &vsJet,
                   const std::string &vsEle,
                   const std::string &vsMu) {
    auto check = [&tau](const std::string &label) -> bool {
      if (label.empty()) {
        return true;
      }
      return tau.isTauIDAvailable(label) && tau.tauID(label) > 0.5f;
    };
    return check("decayModeFindingNewDMs") && tau.decayMode() != 5 && tau.decayMode() != 6 && check(vsJet) &&
           check(vsEle) && check(vsMu);
  }
}  // namespace

class DLSDisappTrkTableProducer : public edm::stream::EDProducer<> {
public:
  explicit DLSDisappTrkTableProducer(const edm::ParameterSet &cfg)
      : tracksToken_(consumes<std::vector<pat::IsolatedTrack>>(cfg.getParameter<edm::InputTag>("tracks"))),
        rhoAllToken_(consumes<double>(cfg.getParameter<edm::InputTag>("rhoAll"))),
        rhoAllCaloToken_(consumes<double>(cfg.getParameter<edm::InputTag>("rhoAllCalo"))),
        rhoCentralCaloToken_(consumes<double>(cfg.getParameter<edm::InputTag>("rhoCentralCalo"))),
        muonsToken_(consumes<std::vector<pat::Muon>>(cfg.getParameter<edm::InputTag>("muons"))),
        verticesToken_(consumes<std::vector<reco::Vertex>>(cfg.getParameter<edm::InputTag>("vertices"))),
        triggerObjectsToken_(consumes<pat::TriggerObjectStandAloneCollection>(cfg.getParameter<edm::InputTag>("triggerObjects"))),
        triggerResultsToken_(consumes<edm::TriggerResults>(cfg.getParameter<edm::InputTag>("triggerResults"))),
        electronsToken_(consumes<std::vector<pat::Electron>>(cfg.getParameter<edm::InputTag>("electrons"))),
        tausToken_(consumes<std::vector<pat::Tau>>(cfg.getParameter<edm::InputTag>("taus"))),
        jetsToken_(consumes<std::vector<pat::Jet>>(cfg.getParameter<edm::InputTag>("jets"))),
        metToken_(consumes<std::vector<pat::MET>>(cfg.getParameter<edm::InputTag>("met"))),
        triggerFilterName_(cfg.getParameter<std::string>("triggerFilterName")),
        electronTriggerFilterName_(cfg.getParameter<std::string>("electronTriggerFilterName")),
        triggerMatchingDR_(cfg.getParameter<double>("triggerMatchingDR")),
        electronIdLabel_(cfg.getParameter<std::string>("electronIdLabel")),
        tauVsJetLabel_(cfg.getParameter<std::string>("tauVsJetLabel")),
        tauVsEleLabel_(cfg.getParameter<std::string>("tauVsEleLabel")),
        tauVsMuLabel_(cfg.getParameter<std::string>("tauVsMuLabel")),
        caloGeometryToken_(esConsumes<edm::Transition::BeginRun>()),
        ecalStatusToken_(esConsumes<edm::Transition::BeginRun>()),
        maskedEcalChannelStatusThreshold_(cfg.getParameter<int>("maskedEcalChannelStatusThreshold")) {
    produces<nanoaod::FlatTable>();
    produces<nanoaod::FlatTable>("muon");
    produces<nanoaod::FlatTable>("ele");
    produces<nanoaod::FlatTable>("tau");
    produces<nanoaod::FlatTable>("jet");
    produces<nanoaod::FlatTable>("vtx");
    produces<nanoaod::FlatTable>("event");
  }

  void beginRun(const edm::Run &, const edm::EventSetup &setup) override {
    maskedEcalChannels_.clear();

    const auto &caloGeometry = setup.getData(caloGeometryToken_);
    const auto &ecalStatus = setup.getData(ecalStatusToken_);

    for (int ieta = -85; ieta <= 85; ++ieta) {
      for (int iphi = 0; iphi <= 360; ++iphi) {
        if (!EBDetId::validDetId(ieta, iphi)) {
          continue;
        }
        const EBDetId detid(ieta, iphi, EBDetId::ETAPHIMODE);
        const auto chit = ecalStatus.find(detid);
        const int status = (chit != ecalStatus.end()) ? chit->getStatusCode() & 0x1F : -1;
        if (status < maskedEcalChannelStatusThreshold_) {
          continue;
        }
        const auto *subGeom = caloGeometry.getSubdetectorGeometry(detid);
        if (subGeom) {
          const auto cellGeom = subGeom->getGeometry(detid);
          maskedEcalChannels_[detid] = std::make_pair(cellGeom->getPosition().eta(), cellGeom->getPosition().phi());
        }
      }
    }

    for (int ix = 0; ix <= 100; ++ix) {
      for (int iy = 0; iy <= 100; ++iy) {
        for (int iz = -1; iz <= 1; iz += 2) {
          if (!EEDetId::validDetId(ix, iy, iz)) {
            continue;
          }
          const EEDetId detid(ix, iy, iz, EEDetId::XYMODE);
          const auto chit = ecalStatus.find(detid);
          const int status = (chit != ecalStatus.end()) ? chit->getStatusCode() & 0x1F : -1;
          if (status < maskedEcalChannelStatusThreshold_) {
            continue;
          }
          const auto *subGeom = caloGeometry.getSubdetectorGeometry(detid);
          if (subGeom) {
            const auto cellGeom = subGeom->getGeometry(detid);
            maskedEcalChannels_[detid] = std::make_pair(cellGeom->getPosition().eta(), cellGeom->getPosition().phi());
          }
        }
      }
    }
  }

  void produce(edm::Event &event, const edm::EventSetup &) override {
    edm::Handle<std::vector<pat::IsolatedTrack>> tracks;
    edm::Handle<double> rhoAll;
    edm::Handle<double> rhoAllCalo;
    edm::Handle<double> rhoCentralCalo;
    edm::Handle<std::vector<pat::Muon>> muons;
    edm::Handle<std::vector<reco::Vertex>> vertices;
    edm::Handle<pat::TriggerObjectStandAloneCollection> triggerObjects;
    edm::Handle<edm::TriggerResults> triggerResults;
    edm::Handle<std::vector<pat::Electron>> electrons;
    edm::Handle<std::vector<pat::Tau>> taus;
    edm::Handle<std::vector<pat::Jet>> jets;
    edm::Handle<std::vector<pat::MET>> mets;
    event.getByToken(tracksToken_, tracks);
    event.getByToken(rhoAllToken_, rhoAll);
    event.getByToken(rhoAllCaloToken_, rhoAllCalo);
    event.getByToken(rhoCentralCaloToken_, rhoCentralCalo);
    event.getByToken(muonsToken_, muons);
    event.getByToken(verticesToken_, vertices);
    event.getByToken(triggerObjectsToken_, triggerObjects);
    event.getByToken(triggerResultsToken_, triggerResults);
    event.getByToken(electronsToken_, electrons);
    event.getByToken(tausToken_, taus);
    event.getByToken(jetsToken_, jets);
    event.getByToken(metToken_, mets);

    const auto &met = mets->at(0);
    float metX = met.pt() * std::cos(met.phi());
    float metY = met.pt() * std::sin(met.phi());
    for (const auto &mu : *muons) {
      metX += mu.pt() * std::cos(mu.phi());
      metY += mu.pt() * std::sin(mu.phi());
    }
    const float metNoMuPt = std::hypot(metX, metY);
    const float metNoMuPhi = std::atan2(metY, metX);

    const auto n = tracks->size();
    std::vector<float> pt, eta, theta, phi, dxy, dxyError, dz, dzError, deltaEta, deltaPhi;
    std::vector<float> dEdxStrip, dEdxPixel, caloEm, caloHad, caloTotal, caloTotNoPU, minDRToMaskedEcal;
    std::vector<float> pfIso, relativePFIso, pfIsoChHad, pfIsoNeutHad, pfIsoPhoton, pfIsoPuChHad;
    std::vector<float> miniIsoChHad, miniIsoNeutHad, miniIsoPhoton, miniIsoPuChHad, miniIsoRelative;
    std::vector<float> dPhiMet, dPhiMetNoMu, ptOverMetNoMu;
    std::vector<int16_t> charge, fromPV, missingInnerHits, missingMiddleHits, hitDropMissingMiddleHits, missingOuterHits;
    std::vector<bool> isHighPurityTrack, isTightTrack, isLooseTrack, hpHasValidHitInPixelLayer;
    std::vector<int16_t> hpNumberOfAllHits, hpNumberOfAllTrackerHits, hpNumberOfValidHits, hpNumberOfValidTrackerHits;
    std::vector<int16_t> validPixelHits, hpNumberOfValidPixelBarrelHits, hpNumberOfValidPixelEndcapHits, hpNumberOfValidStripHits;
    std::vector<int16_t> hpNumberOfValidStripTIBHits, hpNumberOfValidStripTIDHits, hpNumberOfValidStripTOBHits, hpNumberOfValidStripTECHits;
    std::vector<int16_t> hpNumberOfLostHitsTrack, hpNumberOfLostHitsInner, hpNumberOfLostHitsOuter;
    std::vector<int16_t> hpNumberOfLostTrackerHitsTrack, hpNumberOfLostTrackerHitsInner, hpNumberOfLostTrackerHitsOuter;
    std::vector<int16_t> hpNumberOfLostPixelHitsTrack, hpNumberOfLostPixelHitsInner, hpNumberOfLostPixelHitsOuter;
    std::vector<int16_t> hpNumberOfLostPixelBarrelHitsTrack, hpNumberOfLostPixelBarrelHitsInner, hpNumberOfLostPixelBarrelHitsOuter;
    std::vector<int16_t> hpNumberOfLostPixelEndcapHitsTrack, hpNumberOfLostPixelEndcapHitsInner, hpNumberOfLostPixelEndcapHitsOuter;
    std::vector<int16_t> hpNumberOfLostStripHitsTrack, hpNumberOfLostStripHitsInner, hpNumberOfLostStripHitsOuter;
    std::vector<int16_t> hpNumberOfLostStripTIBHitsTrack, hpNumberOfLostStripTIDHitsTrack, hpNumberOfLostStripTOBHitsTrack, hpNumberOfLostStripTECHitsTrack;
    std::vector<int16_t> hpNumberOfInactiveHits, hpNumberOfInactiveTrackerHits, trackerLayersWithMeasurement;
    std::vector<int16_t> hpPixelLayersWithMeasurement, hpStripLayersWithMeasurement, hpPixelBarrelLayersWithMeasurement, hpPixelEndcapLayersWithMeasurement;
    std::vector<int16_t> hpStripTIBLayersWithMeasurement, hpStripTIDLayersWithMeasurement, hpStripTOBLayersWithMeasurement, hpStripTECLayersWithMeasurement;
    std::vector<int16_t> hpTrackerLayersWithoutMeasurementTrack, hpTrackerLayersWithoutMeasurementInner, hpTrackerLayersWithoutMeasurementOuter;
    std::vector<int16_t> hpPixelLayersWithoutMeasurementTrack, hpPixelLayersWithoutMeasurementInner, hpPixelLayersWithoutMeasurementOuter;
    std::vector<int16_t> hpStripLayersWithoutMeasurementTrack, hpStripLayersWithoutMeasurementInner, hpStripLayersWithoutMeasurementOuter;
    std::vector<int16_t> hpPixelBarrelLayersWithoutMeasurementTrack, hpPixelEndcapLayersWithoutMeasurementTrack;
    std::vector<int16_t> hpStripTIBLayersWithoutMeasurementTrack, hpStripTIDLayersWithoutMeasurementTrack, hpStripTOBLayersWithoutMeasurementTrack, hpStripTECLayersWithoutMeasurementTrack;
    std::vector<int16_t> hpTrackerLayersTotallyOffOrBad, hpPixelLayersTotallyOffOrBad, hpStripLayersTotallyOffOrBad;
    std::vector<int16_t> hpPixelBarrelLayersTotallyOffOrBad, hpPixelEndcapLayersTotallyOffOrBad;
    std::vector<int16_t> hpStripTIBLayersTotallyOffOrBad, hpStripTIDLayersTotallyOffOrBad, hpStripTOBLayersTotallyOffOrBad, hpStripTECLayersTotallyOffOrBad;
    std::vector<int16_t> hpTrackerLayersNull, hpPixelLayersNull, hpStripLayersNull;
    std::vector<int16_t> hpNumberOfValidStripLayersWithMonoAndStereo, hpNumberOfValidTIBLayersWithMonoAndStereo;
    std::vector<int16_t> hpNumberOfValidTIDLayersWithMonoAndStereo, hpNumberOfValidTOBLayersWithMonoAndStereo, hpNumberOfValidTECLayersWithMonoAndStereo;

    for (const auto &trk : *tracks) {
      pt.push_back(trk.pt());
      eta.push_back(trk.eta());
      theta.push_back(trk.theta());
      phi.push_back(trk.phi());
      dxy.push_back(trk.dxy());
      dxyError.push_back(trk.dxyError());
      dz.push_back(trk.dz());
      dzError.push_back(trk.dzError());
      charge.push_back(trk.charge());
      fromPV.push_back(trk.fromPV());
      deltaEta.push_back(trk.deltaEta());
      deltaPhi.push_back(trk.deltaPhi());
      isHighPurityTrack.push_back(trk.isHighPurityTrack());
      isTightTrack.push_back(trk.isTightTrack());
      isLooseTrack.push_back(trk.isLooseTrack());
      dEdxStrip.push_back(trk.dEdxStrip());
      dEdxPixel.push_back(trk.dEdxPixel());

      const auto &dr03 = trk.pfIsolationDR03();
      const float absIso = dr03.chargedHadronIso();
      pfIso.push_back(absIso);
      pfIsoChHad.push_back(dr03.chargedHadronIso());
      pfIsoNeutHad.push_back(dr03.neutralHadronIso());
      pfIsoPhoton.push_back(dr03.photonIso());
      pfIsoPuChHad.push_back(dr03.puChargedHadronIso());
      relativePFIso.push_back(trk.pt() > 0.f ? dr03.chargedHadronIso() / trk.pt() : -1.f);

      const auto &mini = trk.miniPFIsolation();
      miniIsoChHad.push_back(mini.chargedHadronIso());
      miniIsoNeutHad.push_back(mini.neutralHadronIso());
      miniIsoPhoton.push_back(mini.photonIso());
      miniIsoPuChHad.push_back(mini.puChargedHadronIso());
      miniIsoRelative.push_back(trk.pt() > 0.f ? mini.chargedHadronIso() / trk.pt() : -1.f);

      const float caloEmValue = trk.matchedCaloJetEmEnergy();
      const float caloHadValue = trk.matchedCaloJetHadEnergy();
      const float caloTot = caloEmValue + caloHadValue;
      caloEm.push_back(caloEmValue);
      caloHad.push_back(caloHadValue);
      caloTotal.push_back(caloTot);
      caloTotNoPU.push_back(std::max(0.f, caloTot - static_cast<float>((*rhoCentralCalo) * M_PI * 0.4 * 0.4)));
      dPhiMet.push_back(reco::deltaPhi(trk.phi(), met.phi()));
      dPhiMetNoMu.push_back(reco::deltaPhi(trk.phi(), metNoMuPhi));
      ptOverMetNoMu.push_back(metNoMuPt > 0.f ? trk.pt() / metNoMuPt : -1.f);

      double minDR = -1.0;
      for (const auto &entry : maskedEcalChannels_) {
        const double dR = reco::deltaR(trk.eta(), trk.phi(), entry.second.first, entry.second.second);
        if (minDR < 0.0 || dR < minDR) {
          minDR = dR;
        }
      }
      minDRToMaskedEcal.push_back(static_cast<float>(minDR));

      const reco::HitPattern &hp = trk.hitPattern();
      using HP = reco::HitPattern;
      const int16_t inner = hp.trackerLayersWithoutMeasurement(HP::MISSING_INNER_HITS);
      const int16_t middle = hp.trackerLayersWithoutMeasurement(HP::TRACK_HITS);
      const int16_t outer = hp.trackerLayersWithoutMeasurement(HP::MISSING_OUTER_HITS);
      missingInnerHits.push_back(inner);
      missingMiddleHits.push_back(middle);
      hitDropMissingMiddleHits.push_back(middle);
      missingOuterHits.push_back(outer);
      hpNumberOfAllHits.push_back(hp.numberOfAllHits(HP::TRACK_HITS));
      hpNumberOfAllTrackerHits.push_back(hp.numberOfAllTrackerHits(HP::TRACK_HITS));
      hpNumberOfValidHits.push_back(hp.numberOfValidHits());
      hpNumberOfValidTrackerHits.push_back(hp.numberOfValidTrackerHits());
      validPixelHits.push_back(hp.numberOfValidPixelHits());
      hpNumberOfValidPixelBarrelHits.push_back(hp.numberOfValidPixelBarrelHits());
      hpNumberOfValidPixelEndcapHits.push_back(hp.numberOfValidPixelEndcapHits());
      hpNumberOfValidStripHits.push_back(hp.numberOfValidStripHits());
      hpNumberOfValidStripTIBHits.push_back(hp.numberOfValidStripTIBHits());
      hpNumberOfValidStripTIDHits.push_back(hp.numberOfValidStripTIDHits());
      hpNumberOfValidStripTOBHits.push_back(hp.numberOfValidStripTOBHits());
      hpNumberOfValidStripTECHits.push_back(hp.numberOfValidStripTECHits());
      hpNumberOfLostHitsTrack.push_back(hp.numberOfLostHits(HP::TRACK_HITS));
      hpNumberOfLostHitsInner.push_back(hp.numberOfLostHits(HP::MISSING_INNER_HITS));
      hpNumberOfLostHitsOuter.push_back(hp.numberOfLostHits(HP::MISSING_OUTER_HITS));
      hpNumberOfLostTrackerHitsTrack.push_back(hp.numberOfLostTrackerHits(HP::TRACK_HITS));
      hpNumberOfLostTrackerHitsInner.push_back(hp.numberOfLostTrackerHits(HP::MISSING_INNER_HITS));
      hpNumberOfLostTrackerHitsOuter.push_back(hp.numberOfLostTrackerHits(HP::MISSING_OUTER_HITS));
      hpNumberOfLostPixelHitsTrack.push_back(hp.numberOfLostPixelHits(HP::TRACK_HITS));
      hpNumberOfLostPixelHitsInner.push_back(hp.numberOfLostPixelHits(HP::MISSING_INNER_HITS));
      hpNumberOfLostPixelHitsOuter.push_back(hp.numberOfLostPixelHits(HP::MISSING_OUTER_HITS));
      hpNumberOfLostPixelBarrelHitsTrack.push_back(hp.numberOfLostPixelBarrelHits(HP::TRACK_HITS));
      hpNumberOfLostPixelBarrelHitsInner.push_back(hp.numberOfLostPixelBarrelHits(HP::MISSING_INNER_HITS));
      hpNumberOfLostPixelBarrelHitsOuter.push_back(hp.numberOfLostPixelBarrelHits(HP::MISSING_OUTER_HITS));
      hpNumberOfLostPixelEndcapHitsTrack.push_back(hp.numberOfLostPixelEndcapHits(HP::TRACK_HITS));
      hpNumberOfLostPixelEndcapHitsInner.push_back(hp.numberOfLostPixelEndcapHits(HP::MISSING_INNER_HITS));
      hpNumberOfLostPixelEndcapHitsOuter.push_back(hp.numberOfLostPixelEndcapHits(HP::MISSING_OUTER_HITS));
      hpNumberOfLostStripHitsTrack.push_back(hp.numberOfLostStripHits(HP::TRACK_HITS));
      hpNumberOfLostStripHitsInner.push_back(hp.numberOfLostStripHits(HP::MISSING_INNER_HITS));
      hpNumberOfLostStripHitsOuter.push_back(hp.numberOfLostStripHits(HP::MISSING_OUTER_HITS));
      hpNumberOfLostStripTIBHitsTrack.push_back(hp.numberOfLostStripTIBHits(HP::TRACK_HITS));
      hpNumberOfLostStripTIDHitsTrack.push_back(hp.numberOfLostStripTIDHits(HP::TRACK_HITS));
      hpNumberOfLostStripTOBHitsTrack.push_back(hp.numberOfLostStripTOBHits(HP::TRACK_HITS));
      hpNumberOfLostStripTECHitsTrack.push_back(hp.numberOfLostStripTECHits(HP::TRACK_HITS));
      hpNumberOfInactiveHits.push_back(hp.numberOfInactiveHits());
      hpNumberOfInactiveTrackerHits.push_back(hp.numberOfInactiveTrackerHits());
      trackerLayersWithMeasurement.push_back(hp.trackerLayersWithMeasurement());
      hpPixelLayersWithMeasurement.push_back(hp.pixelLayersWithMeasurement());
      hpStripLayersWithMeasurement.push_back(hp.stripLayersWithMeasurement());
      hpPixelBarrelLayersWithMeasurement.push_back(hp.pixelBarrelLayersWithMeasurement());
      hpPixelEndcapLayersWithMeasurement.push_back(hp.pixelEndcapLayersWithMeasurement());
      hpStripTIBLayersWithMeasurement.push_back(hp.stripTIBLayersWithMeasurement());
      hpStripTIDLayersWithMeasurement.push_back(hp.stripTIDLayersWithMeasurement());
      hpStripTOBLayersWithMeasurement.push_back(hp.stripTOBLayersWithMeasurement());
      hpStripTECLayersWithMeasurement.push_back(hp.stripTECLayersWithMeasurement());
      hpTrackerLayersWithoutMeasurementTrack.push_back(hp.trackerLayersWithoutMeasurement(HP::TRACK_HITS));
      hpTrackerLayersWithoutMeasurementInner.push_back(hp.trackerLayersWithoutMeasurement(HP::MISSING_INNER_HITS));
      hpTrackerLayersWithoutMeasurementOuter.push_back(hp.trackerLayersWithoutMeasurement(HP::MISSING_OUTER_HITS));
      hpPixelLayersWithoutMeasurementTrack.push_back(hp.pixelLayersWithoutMeasurement(HP::TRACK_HITS));
      hpPixelLayersWithoutMeasurementInner.push_back(hp.pixelLayersWithoutMeasurement(HP::MISSING_INNER_HITS));
      hpPixelLayersWithoutMeasurementOuter.push_back(hp.pixelLayersWithoutMeasurement(HP::MISSING_OUTER_HITS));
      hpStripLayersWithoutMeasurementTrack.push_back(hp.stripLayersWithoutMeasurement(HP::TRACK_HITS));
      hpStripLayersWithoutMeasurementInner.push_back(hp.stripLayersWithoutMeasurement(HP::MISSING_INNER_HITS));
      hpStripLayersWithoutMeasurementOuter.push_back(hp.stripLayersWithoutMeasurement(HP::MISSING_OUTER_HITS));
      hpPixelBarrelLayersWithoutMeasurementTrack.push_back(hp.pixelBarrelLayersWithoutMeasurement(HP::TRACK_HITS));
      hpPixelEndcapLayersWithoutMeasurementTrack.push_back(hp.pixelEndcapLayersWithoutMeasurement(HP::TRACK_HITS));
      hpStripTIBLayersWithoutMeasurementTrack.push_back(hp.stripTIBLayersWithoutMeasurement(HP::TRACK_HITS));
      hpStripTIDLayersWithoutMeasurementTrack.push_back(hp.stripTIDLayersWithoutMeasurement(HP::TRACK_HITS));
      hpStripTOBLayersWithoutMeasurementTrack.push_back(hp.stripTOBLayersWithoutMeasurement(HP::TRACK_HITS));
      hpStripTECLayersWithoutMeasurementTrack.push_back(hp.stripTECLayersWithoutMeasurement(HP::TRACK_HITS));
      hpTrackerLayersTotallyOffOrBad.push_back(hp.trackerLayersTotallyOffOrBad());
      hpPixelLayersTotallyOffOrBad.push_back(hp.pixelLayersTotallyOffOrBad());
      hpStripLayersTotallyOffOrBad.push_back(hp.stripLayersTotallyOffOrBad());
      hpPixelBarrelLayersTotallyOffOrBad.push_back(hp.pixelBarrelLayersTotallyOffOrBad());
      hpPixelEndcapLayersTotallyOffOrBad.push_back(hp.pixelEndcapLayersTotallyOffOrBad());
      hpStripTIBLayersTotallyOffOrBad.push_back(hp.stripTIBLayersTotallyOffOrBad());
      hpStripTIDLayersTotallyOffOrBad.push_back(hp.stripTIDLayersTotallyOffOrBad());
      hpStripTOBLayersTotallyOffOrBad.push_back(hp.stripTOBLayersTotallyOffOrBad());
      hpStripTECLayersTotallyOffOrBad.push_back(hp.stripTECLayersTotallyOffOrBad());
      hpTrackerLayersNull.push_back(hp.trackerLayersNull());
      hpPixelLayersNull.push_back(hp.pixelLayersNull());
      hpStripLayersNull.push_back(hp.stripLayersNull());
      hpHasValidHitInPixelLayer.push_back(hp.hasValidHitInPixelLayer(PixelSubdetector::PixelBarrel, 1));
      hpNumberOfValidStripLayersWithMonoAndStereo.push_back(hp.numberOfValidStripLayersWithMonoAndStereo());
      hpNumberOfValidTIBLayersWithMonoAndStereo.push_back(hp.numberOfValidTIBLayersWithMonoAndStereo());
      hpNumberOfValidTIDLayersWithMonoAndStereo.push_back(hp.numberOfValidTIDLayersWithMonoAndStereo());
      hpNumberOfValidTOBLayersWithMonoAndStereo.push_back(hp.numberOfValidTOBLayersWithMonoAndStereo());
      hpNumberOfValidTECLayersWithMonoAndStereo.push_back(hp.numberOfValidTECLayersWithMonoAndStereo());
    }

    auto table = std::make_unique<nanoaod::FlatTable>(n, "trk", false);
    table->setDoc("DisappTrks compatibility isolated-track table from MiniAOD isolatedTracks");
    addColumn<float>(*table, "pt", pt, "isolated track pt");
    addColumn<float>(*table, "eta", eta, "isolated track eta");
    addColumn<float>(*table, "theta", theta, "isolated track theta");
    addColumn<float>(*table, "phi", phi, "isolated track phi");
    addColumn<int16_t>(*table, "charge", charge, "isolated track charge");
    addColumn<float>(*table, "dxy", dxy, "isolated track dxy");
    addColumn<float>(*table, "dxyError", dxyError, "isolated track dxy uncertainty");
    addColumn<float>(*table, "dz", dz, "isolated track dz");
    addColumn<float>(*table, "dzError", dzError, "isolated track dz uncertainty");
    addColumn<int16_t>(*table, "fromPV", fromPV, "pat::IsolatedTrack fromPV value");
    addColumn<float>(*table, "deltaEta", deltaEta, "pat::IsolatedTrack deltaEta");
    addColumn<float>(*table, "deltaPhi", deltaPhi, "pat::IsolatedTrack deltaPhi");
    addColumn<bool>(*table, "isHighPurityTrack", isHighPurityTrack, "high-purity track quality flag");
    addColumn<bool>(*table, "isTightTrack", isTightTrack, "tight track quality flag");
    addColumn<bool>(*table, "isLooseTrack", isLooseTrack, "loose track quality flag");
    addColumn<float>(*table, "dEdxStrip", dEdxStrip, "strip dE/dx from pat::IsolatedTrack");
    addColumn<float>(*table, "dEdxPixel", dEdxPixel, "pixel dE/dx from pat::IsolatedTrack");
    addColumn<float>(*table, "caloEm", caloEm, "matched calo jet EM energy");
    addColumn<float>(*table, "caloHad", caloHad, "matched calo jet hadronic energy");
    addColumn<float>(*table, "caloTotal", caloTotal, "matched calo jet total energy");
    addColumn<int16_t>(*table, "missingInnerHits", missingInnerHits, "tracker layers without measurement before first hit");
    addColumn<int16_t>(*table, "missingMiddleHits", missingMiddleHits, "tracker layers without measurement on track body");
    addColumn<int16_t>(*table, "hitDrop_missingMiddleHits", hitDropMissingMiddleHits, "missing middle hits; equals old data definition with hitInefficiency=0");
    addColumn<int16_t>(*table, "missingOuterHits", missingOuterHits, "tracker layers without measurement after last hit");
    addColumn<float>(*table, "pfIso", pfIso, "charged DR03 absolute PF isolation");
    addColumn<float>(*table, "relativePFIso", relativePFIso, "charged DR03 relative PF isolation from pat::IsolatedTrack");
    addColumn<float>(*table, "pfIso_chHad", pfIsoChHad, "DR03 charged-hadron PF isolation");
    addColumn<float>(*table, "pfIso_neutHad", pfIsoNeutHad, "DR03 neutral-hadron PF isolation");
    addColumn<float>(*table, "pfIso_photon", pfIsoPhoton, "DR03 photon PF isolation");
    addColumn<float>(*table, "pfIso_puChHad", pfIsoPuChHad, "DR03 pileup charged-hadron PF isolation");
    addColumn<float>(*table, "miniIso_chHad", miniIsoChHad, "mini PF charged-hadron isolation");
    addColumn<float>(*table, "miniIso_neutHad", miniIsoNeutHad, "mini PF neutral-hadron isolation");
    addColumn<float>(*table, "miniIso_photon", miniIsoPhoton, "mini PF photon isolation");
    addColumn<float>(*table, "miniIso_puChHad", miniIsoPuChHad, "mini PF pileup charged-hadron isolation");
    addColumn<float>(*table, "miniIso_relative", miniIsoRelative, "relative mini PF charged-hadron isolation");
    addColumn<float>(*table, "caloTotNoPU", caloTotNoPU, "matched calo energy corrected by central calo rho with dR=0.4");
    addColumn<float>(*table, "minDRToMaskedEcal", minDRToMaskedEcal, "minimum dR to masked ECAL channel from EventSetup status map");
    addColumn<float>(*table, "dPhiMet", dPhiMet, "delta phi between track and corrected MET");
    addColumn<float>(*table, "dPhiMetNoMu", dPhiMetNoMu, "delta phi between track and metNoMu");
    addColumn<float>(*table, "ptOverMetNoMu", ptOverMetNoMu, "track pt divided by metNoMu pt");
    addColumn<int16_t>(*table, "hp_numberOfAllHits", hpNumberOfAllHits, "hitPattern number of all TRACK_HITS hits");
    addColumn<int16_t>(*table, "hp_numberOfAllTrackerHits", hpNumberOfAllTrackerHits, "hitPattern number of all tracker TRACK_HITS hits");
    addColumn<int16_t>(*table, "hp_numberOfValidHits", hpNumberOfValidHits, "hitPattern number of valid hits");
    addColumn<int16_t>(*table, "hp_numberOfValidTrackerHits", hpNumberOfValidTrackerHits, "hitPattern number of valid tracker hits");
    addColumn<int16_t>(*table, "hp_numberOfValidPixelHits", validPixelHits, "hitPattern number of valid pixel hits");
    addColumn<int16_t>(*table, "hp_numberOfValidPixelBarrelHits", hpNumberOfValidPixelBarrelHits, "hitPattern number of valid pixel barrel hits");
    addColumn<int16_t>(*table, "hp_numberOfValidPixelEndcapHits", hpNumberOfValidPixelEndcapHits, "hitPattern number of valid pixel endcap hits");
    addColumn<int16_t>(*table, "hp_numberOfValidStripHits", hpNumberOfValidStripHits, "hitPattern number of valid strip hits");
    addColumn<int16_t>(*table, "hp_numberOfValidStripTIBHits", hpNumberOfValidStripTIBHits, "hitPattern number of valid TIB strip hits");
    addColumn<int16_t>(*table, "hp_numberOfValidStripTIDHits", hpNumberOfValidStripTIDHits, "hitPattern number of valid TID strip hits");
    addColumn<int16_t>(*table, "hp_numberOfValidStripTOBHits", hpNumberOfValidStripTOBHits, "hitPattern number of valid TOB strip hits");
    addColumn<int16_t>(*table, "hp_numberOfValidStripTECHits", hpNumberOfValidStripTECHits, "hitPattern number of valid TEC strip hits");
    addColumn<int16_t>(*table, "hp_numberOfLostHits_TRACK", hpNumberOfLostHitsTrack, "hitPattern lost hits in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostHits_INNER", hpNumberOfLostHitsInner, "hitPattern lost hits in MISSING_INNER_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostHits_OUTER", hpNumberOfLostHitsOuter, "hitPattern lost hits in MISSING_OUTER_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostTrackerHits_TRACK", hpNumberOfLostTrackerHitsTrack, "hitPattern lost tracker hits in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostTrackerHits_INNER", hpNumberOfLostTrackerHitsInner, "hitPattern lost tracker hits in MISSING_INNER_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostTrackerHits_OUTER", hpNumberOfLostTrackerHitsOuter, "hitPattern lost tracker hits in MISSING_OUTER_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostPixelHits_TRACK", hpNumberOfLostPixelHitsTrack, "hitPattern lost pixel hits in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostPixelHits_INNER", hpNumberOfLostPixelHitsInner, "hitPattern lost pixel hits in MISSING_INNER_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostPixelHits_OUTER", hpNumberOfLostPixelHitsOuter, "hitPattern lost pixel hits in MISSING_OUTER_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostPixelBarrelHits_TRACK", hpNumberOfLostPixelBarrelHitsTrack, "hitPattern lost pixel barrel hits in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostPixelBarrelHits_INNER", hpNumberOfLostPixelBarrelHitsInner, "hitPattern lost pixel barrel hits in MISSING_INNER_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostPixelBarrelHits_OUTER", hpNumberOfLostPixelBarrelHitsOuter, "hitPattern lost pixel barrel hits in MISSING_OUTER_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostPixelEndcapHits_TRACK", hpNumberOfLostPixelEndcapHitsTrack, "hitPattern lost pixel endcap hits in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostPixelEndcapHits_INNER", hpNumberOfLostPixelEndcapHitsInner, "hitPattern lost pixel endcap hits in MISSING_INNER_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostPixelEndcapHits_OUTER", hpNumberOfLostPixelEndcapHitsOuter, "hitPattern lost pixel endcap hits in MISSING_OUTER_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostStripHits_TRACK", hpNumberOfLostStripHitsTrack, "hitPattern lost strip hits in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostStripHits_INNER", hpNumberOfLostStripHitsInner, "hitPattern lost strip hits in MISSING_INNER_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostStripHits_OUTER", hpNumberOfLostStripHitsOuter, "hitPattern lost strip hits in MISSING_OUTER_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostStripTIBHits_TRACK", hpNumberOfLostStripTIBHitsTrack, "hitPattern lost TIB strip hits in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostStripTIDHits_TRACK", hpNumberOfLostStripTIDHitsTrack, "hitPattern lost TID strip hits in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostStripTOBHits_TRACK", hpNumberOfLostStripTOBHitsTrack, "hitPattern lost TOB strip hits in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfLostStripTECHits_TRACK", hpNumberOfLostStripTECHitsTrack, "hitPattern lost TEC strip hits in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_numberOfInactiveHits", hpNumberOfInactiveHits, "hitPattern inactive hits");
    addColumn<int16_t>(*table, "hp_numberOfInactiveTrackerHits", hpNumberOfInactiveTrackerHits, "hitPattern inactive tracker hits");
    addColumn<int16_t>(*table, "hp_trackerLayersWithMeasurement", trackerLayersWithMeasurement, "hitPattern tracker layers with measurement");
    addColumn<int16_t>(*table, "hp_pixelLayersWithMeasurement", hpPixelLayersWithMeasurement, "hitPattern pixel layers with measurement");
    addColumn<int16_t>(*table, "hp_stripLayersWithMeasurement", hpStripLayersWithMeasurement, "hitPattern strip layers with measurement");
    addColumn<int16_t>(*table, "hp_pixelBarrelLayersWithMeasurement", hpPixelBarrelLayersWithMeasurement, "hitPattern pixel barrel layers with measurement");
    addColumn<int16_t>(*table, "hp_pixelEndcapLayersWithMeasurement", hpPixelEndcapLayersWithMeasurement, "hitPattern pixel endcap layers with measurement");
    addColumn<int16_t>(*table, "hp_stripTIBLayersWithMeasurement", hpStripTIBLayersWithMeasurement, "hitPattern TIB strip layers with measurement");
    addColumn<int16_t>(*table, "hp_stripTIDLayersWithMeasurement", hpStripTIDLayersWithMeasurement, "hitPattern TID strip layers with measurement");
    addColumn<int16_t>(*table, "hp_stripTOBLayersWithMeasurement", hpStripTOBLayersWithMeasurement, "hitPattern TOB strip layers with measurement");
    addColumn<int16_t>(*table, "hp_stripTECLayersWithMeasurement", hpStripTECLayersWithMeasurement, "hitPattern TEC strip layers with measurement");
    addColumn<int16_t>(*table, "hp_trackerLayersWithoutMeasurement_TRACK", hpTrackerLayersWithoutMeasurementTrack, "tracker layers without measurement in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_trackerLayersWithoutMeasurement_INNER", hpTrackerLayersWithoutMeasurementInner, "tracker layers without measurement in MISSING_INNER_HITS category");
    addColumn<int16_t>(*table, "hp_trackerLayersWithoutMeasurement_OUTER", hpTrackerLayersWithoutMeasurementOuter, "tracker layers without measurement in MISSING_OUTER_HITS category");
    addColumn<int16_t>(*table, "hp_pixelLayersWithoutMeasurement_TRACK", hpPixelLayersWithoutMeasurementTrack, "pixel layers without measurement in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_pixelLayersWithoutMeasurement_INNER", hpPixelLayersWithoutMeasurementInner, "pixel layers without measurement in MISSING_INNER_HITS category");
    addColumn<int16_t>(*table, "hp_pixelLayersWithoutMeasurement_OUTER", hpPixelLayersWithoutMeasurementOuter, "pixel layers without measurement in MISSING_OUTER_HITS category");
    addColumn<int16_t>(*table, "hp_stripLayersWithoutMeasurement_TRACK", hpStripLayersWithoutMeasurementTrack, "strip layers without measurement in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_stripLayersWithoutMeasurement_INNER", hpStripLayersWithoutMeasurementInner, "strip layers without measurement in MISSING_INNER_HITS category");
    addColumn<int16_t>(*table, "hp_stripLayersWithoutMeasurement_OUTER", hpStripLayersWithoutMeasurementOuter, "strip layers without measurement in MISSING_OUTER_HITS category");
    addColumn<int16_t>(*table, "hp_pixelBarrelLayersWithoutMeasurement_TRACK", hpPixelBarrelLayersWithoutMeasurementTrack, "pixel barrel layers without measurement in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_pixelEndcapLayersWithoutMeasurement_TRACK", hpPixelEndcapLayersWithoutMeasurementTrack, "pixel endcap layers without measurement in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_stripTIBLayersWithoutMeasurement_TRACK", hpStripTIBLayersWithoutMeasurementTrack, "TIB strip layers without measurement in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_stripTIDLayersWithoutMeasurement_TRACK", hpStripTIDLayersWithoutMeasurementTrack, "TID strip layers without measurement in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_stripTOBLayersWithoutMeasurement_TRACK", hpStripTOBLayersWithoutMeasurementTrack, "TOB strip layers without measurement in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_stripTECLayersWithoutMeasurement_TRACK", hpStripTECLayersWithoutMeasurementTrack, "TEC strip layers without measurement in TRACK_HITS category");
    addColumn<int16_t>(*table, "hp_trackerLayersTotallyOffOrBad", hpTrackerLayersTotallyOffOrBad, "hitPattern tracker layers totally off or bad");
    addColumn<int16_t>(*table, "hp_pixelLayersTotallyOffOrBad", hpPixelLayersTotallyOffOrBad, "hitPattern pixel layers totally off or bad");
    addColumn<int16_t>(*table, "hp_stripLayersTotallyOffOrBad", hpStripLayersTotallyOffOrBad, "hitPattern strip layers totally off or bad");
    addColumn<int16_t>(*table, "hp_pixelBarrelLayersTotallyOffOrBad", hpPixelBarrelLayersTotallyOffOrBad, "hitPattern pixel barrel layers totally off or bad");
    addColumn<int16_t>(*table, "hp_pixelEndcapLayersTotallyOffOrBad", hpPixelEndcapLayersTotallyOffOrBad, "hitPattern pixel endcap layers totally off or bad");
    addColumn<int16_t>(*table, "hp_stripTIBLayersTotallyOffOrBad", hpStripTIBLayersTotallyOffOrBad, "hitPattern TIB strip layers totally off or bad");
    addColumn<int16_t>(*table, "hp_stripTIDLayersTotallyOffOrBad", hpStripTIDLayersTotallyOffOrBad, "hitPattern TID strip layers totally off or bad");
    addColumn<int16_t>(*table, "hp_stripTOBLayersTotallyOffOrBad", hpStripTOBLayersTotallyOffOrBad, "hitPattern TOB strip layers totally off or bad");
    addColumn<int16_t>(*table, "hp_stripTECLayersTotallyOffOrBad", hpStripTECLayersTotallyOffOrBad, "hitPattern TEC strip layers totally off or bad");
    addColumn<int16_t>(*table, "hp_trackerLayersNull", hpTrackerLayersNull, "hitPattern tracker layers null");
    addColumn<int16_t>(*table, "hp_pixelLayersNull", hpPixelLayersNull, "hitPattern pixel layers null");
    addColumn<int16_t>(*table, "hp_stripLayersNull", hpStripLayersNull, "hitPattern strip layers null");
    addColumn<bool>(*table, "hp_hasValidHitInPixelLayer", hpHasValidHitInPixelLayer, "valid hit in pixel barrel layer 1");
    addColumn<int16_t>(*table, "hp_numberOfValidStripLayersWithMonoAndStereo", hpNumberOfValidStripLayersWithMonoAndStereo, "valid strip layers with mono and stereo");
    addColumn<int16_t>(*table, "hp_numberOfValidTIBLayersWithMonoAndStereo", hpNumberOfValidTIBLayersWithMonoAndStereo, "valid TIB layers with mono and stereo");
    addColumn<int16_t>(*table, "hp_numberOfValidTIDLayersWithMonoAndStereo", hpNumberOfValidTIDLayersWithMonoAndStereo, "valid TID layers with mono and stereo");
    addColumn<int16_t>(*table, "hp_numberOfValidTOBLayersWithMonoAndStereo", hpNumberOfValidTOBLayersWithMonoAndStereo, "valid TOB layers with mono and stereo");
    addColumn<int16_t>(*table, "hp_numberOfValidTECLayersWithMonoAndStereo", hpNumberOfValidTECLayersWithMonoAndStereo, "valid TEC layers with mono and stereo");
    event.put(std::move(table));

    const auto trigEtaPhi = triggerObjectEtaPhi(*triggerObjects, event, *triggerResults, triggerFilterName_);
    const auto eleTrigEtaPhi = triggerObjectEtaPhi(*triggerObjects, event, *triggerResults, electronTriggerFilterName_);
    const reco::Vertex *pv = vertices->empty() ? nullptr : &vertices->front();
    {
      std::vector<float> muPt, muEta, muPhi, muPfRelIso04DBeta;
      std::vector<int16_t> muCharge;
      std::vector<bool> muTrig, muTight;
      for (const auto &mu : *muons) {
        muPt.push_back(mu.pt());
        muEta.push_back(mu.eta());
        muPhi.push_back(mu.phi());
        muCharge.push_back(mu.charge());
        muTrig.push_back(matchedToTriggerObject(mu, trigEtaPhi, triggerMatchingDR_));
        muTight.push_back(pv && mu.isTightMuon(*pv));
        const auto &iso4 = mu.pfIsolationR04();
        const float absIso = iso4.sumChargedHadronPt +
                             std::max(0.f, iso4.sumNeutralHadronEt + iso4.sumPhotonEt - 0.5f * iso4.sumPUPt);
        muPfRelIso04DBeta.push_back(mu.pt() > 0.f ? absIso / mu.pt() : -1.f);
      }
      auto out = std::make_unique<nanoaod::FlatTable>(muons->size(), "muon", false);
      out->setDoc("DisappTrks muon extras from slimmedMuons");
      addColumn<bool>(*out, "isTrigMatched", muTrig, "matched to configured muon HLT filter object");
      addColumn<float>(*out, "pfRelIso04_dBeta", muPfRelIso04DBeta, "delta-beta corrected PF relative isolation with dR=0.4");
      event.put(std::move(out), "muon");
    }

    {
      std::vector<float> elePt, eleEta, elePhi, elePfRelIso04DBeta;
      std::vector<int16_t> eleCharge;
      std::vector<bool> eleTrig, eleTight;
      for (const auto &ele : *electrons) {
        elePt.push_back(ele.pt());
        eleEta.push_back(ele.eta());
        elePhi.push_back(ele.phi());
        eleCharge.push_back(ele.charge());
        eleTrig.push_back(matchedToTriggerObject(ele, eleTrigEtaPhi, triggerMatchingDR_));
        eleTight.push_back(ele.isElectronIDAvailable(electronIdLabel_) && ele.electronID(electronIdLabel_) > 0.5f);
        elePfRelIso04DBeta.push_back(-1.f);
      }
      auto out = std::make_unique<nanoaod::FlatTable>(electrons->size(), "ele", false);
      out->setDoc("DisappTrks electron extras from slimmedElectrons");
      addColumn<bool>(*out, "isTrigMatched", eleTrig, "matched to configured electron HLT filter object");
      event.put(std::move(out), "ele");
    }

    {
      std::vector<float> tauPt, tauEta, tauPhi, tauPfRelIso04DBeta, tauDeepVsJet, tauDeepVsEle, tauDeepVsMu;
      std::vector<int16_t> tauCharge, tauDecayMode;
      std::vector<bool> tauTrig, tauTight, tauDecayModeFindingNewDMs;
      for (const auto &tau : *taus) {
        tauPt.push_back(tau.pt());
        tauEta.push_back(tau.eta());
        tauPhi.push_back(tau.phi());
        tauCharge.push_back(tau.charge());
        tauTrig.push_back(false);
        tauTight.push_back(tauPassesId(tau, tauVsJetLabel_, tauVsEleLabel_, tauVsMuLabel_));
        tauPfRelIso04DBeta.push_back(-1.f);
        tauDecayMode.push_back(tau.decayMode());
        tauDecayModeFindingNewDMs.push_back(tauIdValue(tau, "decayModeFindingNewDMs") > 0.5f);
        tauDeepVsJet.push_back(tauIdValue(tau, "byDeepTau2018v2p5VSjetraw"));
        tauDeepVsEle.push_back(tauIdValue(tau, "byDeepTau2018v2p5VSeraw"));
        tauDeepVsMu.push_back(tauIdValue(tau, "byDeepTau2018v2p5VSmuraw"));
      }
      auto out = std::make_unique<nanoaod::FlatTable>(taus->size(), "tau", false);
      out->setDoc("DisappTrks tau extras from slimmedTaus");
      addColumn<bool>(*out, "isTight", tauTight, "configured tau ID combination");
      addColumn<bool>(*out, "decayModeFindingNewDMs", tauDecayModeFindingNewDMs, "tau decayModeFindingNewDMs ID flag");
      event.put(std::move(out), "tau");
    }

    {
      std::vector<float> jetPt, jetEta, jetPhi, jetEnergy;
      std::vector<bool> jetTightLepVeto;
      for (const auto &jet : *jets) {
        jetPt.push_back(jet.pt());
        jetEta.push_back(jet.eta());
        jetPhi.push_back(jet.phi());
        jetEnergy.push_back(jet.energy());
        jetTightLepVeto.push_back(passesTightLepVetoJetId(jet));
      }
      auto out = std::make_unique<nanoaod::FlatTable>(jets->size(), "jet", false);
      out->setDoc("DisappTrks jet extras from corrected or slimmed jets");
      addColumn<bool>(*out, "isTightLepVeto", jetTightLepVeto, "old ntuplizer inline tight lepton veto ID");
      event.put(std::move(out), "jet");
    }

    {
      std::vector<float> vtxX, vtxY, vtxZ, vtxXError, vtxYError, vtxZError, vtxChi2, vtxNormalizedChi2, vtxNdof;
      std::vector<int16_t> vtxNTracks;
      std::vector<bool> vtxIsValid, vtxIsFake;
      for (const auto &vertex : *vertices) {
        vtxX.push_back(vertex.x());
        vtxY.push_back(vertex.y());
        vtxZ.push_back(vertex.z());
        vtxXError.push_back(vertex.xError());
        vtxYError.push_back(vertex.yError());
        vtxZError.push_back(vertex.zError());
        vtxChi2.push_back(vertex.chi2());
        vtxNormalizedChi2.push_back(vertex.normalizedChi2());
        vtxNdof.push_back(vertex.ndof());
        vtxNTracks.push_back(vertex.nTracks());
        vtxIsValid.push_back(vertex.isValid());
        vtxIsFake.push_back(vertex.isFake());
      }
      auto out = std::make_unique<nanoaod::FlatTable>(vertices->size(), "vtx", false);
      out->setDoc("DisappTrks compatibility primary vertex table from offlineSlimmedPrimaryVertices");
      addColumn<float>(*out, "x", vtxX, "primary vertex x");
      addColumn<float>(*out, "y", vtxY, "primary vertex y");
      addColumn<float>(*out, "z", vtxZ, "primary vertex z");
      addColumn<float>(*out, "xError", vtxXError, "primary vertex x uncertainty");
      addColumn<float>(*out, "yError", vtxYError, "primary vertex y uncertainty");
      addColumn<float>(*out, "zError", vtxZError, "primary vertex z uncertainty");
      addColumn<float>(*out, "chi2", vtxChi2, "primary vertex chi2");
      addColumn<float>(*out, "normalizedChi2", vtxNormalizedChi2, "primary vertex normalized chi2");
      addColumn<float>(*out, "ndof", vtxNdof, "primary vertex ndof");
      addColumn<int16_t>(*out, "nTracks", vtxNTracks, "primary vertex nTracks");
      addColumn<bool>(*out, "isValid", vtxIsValid, "primary vertex validity flag");
      addColumn<bool>(*out, "isFake", vtxIsFake, "primary vertex fake flag");
      event.put(std::move(out), "vtx");
    }

    auto eventTable = std::make_unique<nanoaod::FlatTable>(1, "", true);
    eventTable->setDoc("DisappTrks singleton event variables");
    eventTable->addColumnValue<float>("metNoMu_pt", metNoMuPt, "MET with muon momenta added back");
    eventTable->addColumnValue<float>("metNoMu_phi", metNoMuPhi, "phi of MET with muon momenta added back");
    event.put(std::move(eventTable), "event");
  }

  static void fillDescriptions(edm::ConfigurationDescriptions &descriptions) {
    edm::ParameterSetDescription desc;
    desc.add<edm::InputTag>("tracks", edm::InputTag("isolatedTracks"));
    desc.add<edm::InputTag>("rhoAll", edm::InputTag("fixedGridRhoFastjetAll"));
    desc.add<edm::InputTag>("rhoAllCalo", edm::InputTag("fixedGridRhoFastjetAllCalo"));
    desc.add<edm::InputTag>("rhoCentralCalo", edm::InputTag("fixedGridRhoFastjetCentralCalo"));
    desc.add<edm::InputTag>("muons", edm::InputTag("slimmedMuons"));
    desc.add<edm::InputTag>("vertices", edm::InputTag("offlineSlimmedPrimaryVertices"));
    desc.add<edm::InputTag>("triggerObjects", edm::InputTag("slimmedPatTrigger"));
    desc.add<edm::InputTag>("triggerResults", edm::InputTag("TriggerResults", "", "HLT"));
    desc.add<edm::InputTag>("electrons", edm::InputTag("slimmedElectrons"));
    desc.add<edm::InputTag>("taus", edm::InputTag("slimmedTaus"));
    desc.add<edm::InputTag>("jets", edm::InputTag("slimmedJets"));
    desc.add<edm::InputTag>("met", edm::InputTag("slimmedMETs"));
    desc.add<std::string>("triggerFilterName", "hltL3crIsoL1sSingleMu22L1f0L2f10QL3f24QL3trkIsoFiltered");
    desc.add<std::string>("electronTriggerFilterName", "hltEle32WPTightGsfTrackIsoFilter");
    desc.add<double>("triggerMatchingDR", 0.3);
    desc.add<std::string>("electronIdLabel", "cutBasedElectronID-RunIIIWinter22-V1-tight");
    desc.add<std::string>("tauVsJetLabel", "");
    desc.add<std::string>("tauVsEleLabel", "byVVVLooseDeepTau2018v2p5VSe");
    desc.add<std::string>("tauVsMuLabel", "byVLooseDeepTau2018v2p5VSmu");
    desc.add<int>("maskedEcalChannelStatusThreshold", 3);
    descriptions.add("disappTrkTable", desc);
  }

private:
  edm::EDGetTokenT<std::vector<pat::IsolatedTrack>> tracksToken_;
  edm::EDGetTokenT<double> rhoAllToken_;
  edm::EDGetTokenT<double> rhoAllCaloToken_;
  edm::EDGetTokenT<double> rhoCentralCaloToken_;
  edm::EDGetTokenT<std::vector<pat::Muon>> muonsToken_;
  edm::EDGetTokenT<std::vector<reco::Vertex>> verticesToken_;
  edm::EDGetTokenT<pat::TriggerObjectStandAloneCollection> triggerObjectsToken_;
  edm::EDGetTokenT<edm::TriggerResults> triggerResultsToken_;
  edm::EDGetTokenT<std::vector<pat::Electron>> electronsToken_;
  edm::EDGetTokenT<std::vector<pat::Tau>> tausToken_;
  edm::EDGetTokenT<std::vector<pat::Jet>> jetsToken_;
  edm::EDGetTokenT<std::vector<pat::MET>> metToken_;
  std::string triggerFilterName_;
  std::string electronTriggerFilterName_;
  double triggerMatchingDR_;
  std::string electronIdLabel_;
  std::string tauVsJetLabel_;
  std::string tauVsEleLabel_;
  std::string tauVsMuLabel_;
  edm::ESGetToken<CaloGeometry, CaloGeometryRecord> caloGeometryToken_;
  edm::ESGetToken<EcalChannelStatus, EcalChannelStatusRcd> ecalStatusToken_;
  int maskedEcalChannelStatusThreshold_;
  std::map<DetId, std::pair<double, double>> maskedEcalChannels_;
};

class DLSDisappMuonTableProducer : public edm::stream::EDProducer<> {
public:
  explicit DLSDisappMuonTableProducer(const edm::ParameterSet &cfg)
      : muonsToken_(consumes<std::vector<pat::Muon>>(cfg.getParameter<edm::InputTag>("muons"))),
        verticesToken_(consumes<std::vector<reco::Vertex>>(cfg.getParameter<edm::InputTag>("vertices"))),
        triggerObjectsToken_(consumes<pat::TriggerObjectStandAloneCollection>(cfg.getParameter<edm::InputTag>("triggerObjects"))),
        triggerResultsToken_(consumes<edm::TriggerResults>(cfg.getParameter<edm::InputTag>("triggerResults"))),
        triggerFilterName_(cfg.getParameter<std::string>("triggerFilterName")),
        triggerMatchingDR_(cfg.getParameter<double>("triggerMatchingDR")) {
    produces<nanoaod::FlatTable>();
  }

  void produce(edm::Event &event, const edm::EventSetup &) override {
    edm::Handle<std::vector<pat::Muon>> muons;
    edm::Handle<std::vector<reco::Vertex>> vertices;
    edm::Handle<pat::TriggerObjectStandAloneCollection> triggerObjects;
    edm::Handle<edm::TriggerResults> triggerResults;
    event.getByToken(muonsToken_, muons);
    event.getByToken(verticesToken_, vertices);
    event.getByToken(triggerObjectsToken_, triggerObjects);
    event.getByToken(triggerResultsToken_, triggerResults);
    const auto trigEtaPhi = triggerObjectEtaPhi(*triggerObjects, event, *triggerResults, triggerFilterName_);
    const reco::Vertex *pv = vertices->empty() ? nullptr : &vertices->front();

    const auto n = muons->size();
    std::vector<float> pt, eta, phi;
    std::vector<int16_t> charge;
    std::vector<bool> isTrigMatched, isTight;
    pt.reserve(n);
    eta.reserve(n);
    phi.reserve(n);
    charge.reserve(n);
    isTrigMatched.reserve(n);
    isTight.reserve(n);

    for (const auto &mu : *muons) {
      pt.push_back(mu.pt());
      eta.push_back(mu.eta());
      phi.push_back(mu.phi());
      charge.push_back(mu.charge());
      isTrigMatched.push_back(matchedToTriggerObject(mu, trigEtaPhi, triggerMatchingDR_));
      isTight.push_back(pv && mu.isTightMuon(*pv));
    }

    auto table = std::make_unique<nanoaod::FlatTable>(n, "muon", false);
    table->setDoc("DisappTrks compatibility muon table from slimmedMuons");
    addColumn<float>(*table, "pt", pt, "muon pt");
    addColumn<float>(*table, "eta", eta, "muon eta");
    addColumn<float>(*table, "phi", phi, "muon phi");
    addColumn<int16_t>(*table, "charge", charge, "muon charge");
    addColumn<bool>(*table, "isTrigMatched", isTrigMatched, "matched to configured muon HLT filter object");
    addColumn<bool>(*table, "isTight", isTight, "pat::Muon tight ID with first PV");
    event.put(std::move(table));
  }

  static void fillDescriptions(edm::ConfigurationDescriptions &descriptions) {
    edm::ParameterSetDescription desc;
    desc.add<edm::InputTag>("muons", edm::InputTag("slimmedMuons"));
    desc.add<edm::InputTag>("vertices", edm::InputTag("offlineSlimmedPrimaryVertices"));
    desc.add<edm::InputTag>("triggerObjects", edm::InputTag("slimmedPatTrigger"));
    desc.add<edm::InputTag>("triggerResults", edm::InputTag("TriggerResults", "", "HLT"));
    desc.add<std::string>("triggerFilterName", "hltL3crIsoL1sSingleMu22L1f0L2f10QL3f24QL3trkIsoFiltered");
    desc.add<double>("triggerMatchingDR", 0.3);
    descriptions.add("disappMuonTable", desc);
  }

private:
  edm::EDGetTokenT<std::vector<pat::Muon>> muonsToken_;
  edm::EDGetTokenT<std::vector<reco::Vertex>> verticesToken_;
  edm::EDGetTokenT<pat::TriggerObjectStandAloneCollection> triggerObjectsToken_;
  edm::EDGetTokenT<edm::TriggerResults> triggerResultsToken_;
  std::string triggerFilterName_;
  double triggerMatchingDR_;
};

class DLSDisappObjectTablesProducer : public edm::stream::EDProducer<> {
public:
  explicit DLSDisappObjectTablesProducer(const edm::ParameterSet &cfg)
      : electronsToken_(consumes<std::vector<pat::Electron>>(cfg.getParameter<edm::InputTag>("electrons"))),
        tausToken_(consumes<std::vector<pat::Tau>>(cfg.getParameter<edm::InputTag>("taus"))),
        jetsToken_(consumes<std::vector<pat::Jet>>(cfg.getParameter<edm::InputTag>("jets"))),
        electronIdLabel_(cfg.getParameter<std::string>("electronIdLabel")) {
    produces<nanoaod::FlatTable>("ele");
    produces<nanoaod::FlatTable>("tau");
    produces<nanoaod::FlatTable>("jet");
  }

  void produce(edm::Event &event, const edm::EventSetup &) override {
    edm::Handle<std::vector<pat::Electron>> electrons;
    edm::Handle<std::vector<pat::Tau>> taus;
    edm::Handle<std::vector<pat::Jet>> jets;
    event.getByToken(electronsToken_, electrons);
    event.getByToken(tausToken_, taus);
    event.getByToken(jetsToken_, jets);

    {
      std::vector<float> pt, eta, phi;
      std::vector<bool> isTight;
      for (const auto &ele : *electrons) {
        pt.push_back(ele.pt());
        eta.push_back(ele.eta());
        phi.push_back(ele.phi());
        isTight.push_back(ele.isElectronIDAvailable(electronIdLabel_) && ele.electronID(electronIdLabel_) > 0.5f);
      }
      auto table = std::make_unique<nanoaod::FlatTable>(electrons->size(), "ele", false);
      table->setDoc("DisappTrks compatibility electron table from slimmedElectrons");
      addColumn<float>(*table, "pt", pt, "electron pt");
      addColumn<float>(*table, "eta", eta, "electron eta");
      addColumn<float>(*table, "phi", phi, "electron phi");
      addColumn<bool>(*table, "isTight", isTight, "configured cut-based tight electron ID");
      event.put(std::move(table), "ele");
    }

    {
      std::vector<float> eta, phi;
      for (const auto &tau : *taus) {
        eta.push_back(tau.eta());
        phi.push_back(tau.phi());
      }
      auto table = std::make_unique<nanoaod::FlatTable>(taus->size(), "tau", false);
      table->setDoc("DisappTrks compatibility tau table from slimmedTaus");
      addColumn<float>(*table, "eta", eta, "tau eta");
      addColumn<float>(*table, "phi", phi, "tau phi");
      event.put(std::move(table), "tau");
    }

    {
      std::vector<float> pt, eta, phi;
      std::vector<bool> isTightLepVeto;
      for (const auto &jet : *jets) {
        pt.push_back(jet.pt());
        eta.push_back(jet.eta());
        phi.push_back(jet.phi());
        isTightLepVeto.push_back(passesTightLepVetoJetId(jet));
      }
      auto table = std::make_unique<nanoaod::FlatTable>(jets->size(), "jet", false);
      table->setDoc("DisappTrks compatibility jet table from corrected or slimmed jets");
      addColumn<float>(*table, "pt", pt, "jet pt");
      addColumn<float>(*table, "eta", eta, "jet eta");
      addColumn<float>(*table, "phi", phi, "jet phi");
      addColumn<bool>(*table, "isTightLepVeto", isTightLepVeto, "pat::Jet tight lepton veto ID");
      event.put(std::move(table), "jet");
    }
  }

  static void fillDescriptions(edm::ConfigurationDescriptions &descriptions) {
    edm::ParameterSetDescription desc;
    desc.add<edm::InputTag>("electrons", edm::InputTag("slimmedElectrons"));
    desc.add<edm::InputTag>("taus", edm::InputTag("slimmedTaus"));
    desc.add<edm::InputTag>("jets", edm::InputTag("slimmedJets"));
    desc.add<std::string>("electronIdLabel", "cutBasedElectronID-RunIIIWinter22-V1-tight");
    descriptions.add("disappObjectTables", desc);
  }

private:
  edm::EDGetTokenT<std::vector<pat::Electron>> electronsToken_;
  edm::EDGetTokenT<std::vector<pat::Tau>> tausToken_;
  edm::EDGetTokenT<std::vector<pat::Jet>> jetsToken_;
  std::string electronIdLabel_;
};

class DLSDisappMetNoMuTableProducer : public edm::stream::EDProducer<> {
public:
  explicit DLSDisappMetNoMuTableProducer(const edm::ParameterSet &cfg)
      : metToken_(consumes<std::vector<pat::MET>>(cfg.getParameter<edm::InputTag>("met"))),
        muonsToken_(consumes<std::vector<pat::Muon>>(cfg.getParameter<edm::InputTag>("muons"))) {
    produces<nanoaod::FlatTable>();
  }

  void produce(edm::Event &event, const edm::EventSetup &) override {
    edm::Handle<std::vector<pat::MET>> mets;
    edm::Handle<std::vector<pat::Muon>> muons;
    event.getByToken(metToken_, mets);
    event.getByToken(muonsToken_, muons);
    const auto &met = mets->at(0);
    float metX = met.pt() * std::cos(met.phi());
    float metY = met.pt() * std::sin(met.phi());
    for (const auto &mu : *muons) {
      metX += mu.pt() * std::cos(mu.phi());
      metY += mu.pt() * std::sin(mu.phi());
    }
    auto table = std::make_unique<nanoaod::FlatTable>(1, "", true);
    table->setDoc("DisappTrks singleton event variables");
    table->addColumnValue<float>("metNoMu_pt", std::hypot(metX, metY), "MET with muon momenta added back");
    table->addColumnValue<float>("metNoMu_phi", std::atan2(metY, metX), "phi of MET with muon momenta added back");
    event.put(std::move(table));
  }

  static void fillDescriptions(edm::ConfigurationDescriptions &descriptions) {
    edm::ParameterSetDescription desc;
    desc.add<edm::InputTag>("met", edm::InputTag("slimmedMETs"));
    desc.add<edm::InputTag>("muons", edm::InputTag("slimmedMuons"));
    descriptions.add("disappMetNoMuTable", desc);
  }

private:
  edm::EDGetTokenT<std::vector<pat::MET>> metToken_;
  edm::EDGetTokenT<std::vector<pat::Muon>> muonsToken_;
};

DEFINE_FWK_MODULE(DLSDisappTrkTableProducer);
DEFINE_FWK_MODULE(DLSDisappMuonTableProducer);
DEFINE_FWK_MODULE(DLSDisappObjectTablesProducer);
DEFINE_FWK_MODULE(DLSDisappMetNoMuTableProducer);
