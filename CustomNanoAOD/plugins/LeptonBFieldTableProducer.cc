// Stores bField_z: the z-component of the CMS magnetic field (in GeV/cm,
// matching CMSSW's inInverseGeV convention) evaluated at each lepton's track
// reference point. This is the value used by TwoTrackMinimumDistanceHelixHelix
// and PerigeeLinearizedTrackState when computing helix radii and Jacobians.
//
// Templated on lepton type; explicit specialisations for pat::Muon
// (innerTrack) and pat::Electron (gsfTrack) are registered as separate plugins.
//
// Uses the ESHandle API for compatibility with CMSSW 10_2_x and later.

#include "FWCore/Framework/interface/stream/EDProducer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/ESHandle.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/Utilities/interface/EDGetToken.h"
#include "DataFormats/PatCandidates/interface/Muon.h"
#include "DataFormats/PatCandidates/interface/Electron.h"
#include "DataFormats/NanoAOD/interface/FlatTable.h"
#include "DataFormats/GeometryVector/interface/GlobalPoint.h"
#include "MagneticField/Engine/interface/MagneticField.h"
#include "MagneticField/Records/interface/IdealMagneticFieldRecord.h"

template <typename T>
class LeptonBFieldTableProducer : public edm::stream::EDProducer<> {
public:
    explicit LeptonBFieldTableProducer(const edm::ParameterSet& iConfig)
        : srcToken_(consumes<std::vector<T>>(iConfig.getParameter<edm::InputTag>("src"))),
          name_(iConfig.getParameter<std::string>("name")) {
        produces<nanoaod::FlatTable>();
    }

    void produce(edm::Event& iEvent, const edm::EventSetup& iSetup) override {
        edm::Handle<std::vector<T>> leptons;
        iEvent.getByToken(srcToken_, leptons);

        edm::ESHandle<MagneticField> bField;
        iSetup.get<IdealMagneticFieldRecord>().get(bField);

        std::vector<float> bField_z;
        bField_z.reserve(leptons->size());

        for (const auto& lepton : *leptons) {
            const reco::Track* trk = getTrack(lepton);
            if (trk) {
                GlobalPoint pos(trk->vx(), trk->vy(), trk->vz());
                bField_z.push_back(bField->inInverseGeV(pos).z());
            } else {
                bField_z.push_back(0.f);
            }
        }

        auto table = std::make_unique<nanoaod::FlatTable>(leptons->size(), name_, false, true);
        table->addColumn<float>("bField_z", bField_z,
            "z component of magnetic field at track ref. point [GeV/cm]", 10);
        iEvent.put(std::move(table));
    }

private:
    const reco::Track* getTrack(const T& lepton) const;

    edm::EDGetTokenT<std::vector<T>> srcToken_;
    std::string name_;
};

template <>
const reco::Track* LeptonBFieldTableProducer<pat::Muon>::getTrack(const pat::Muon& mu) const {
    return mu.innerTrack().isNonnull() ? mu.innerTrack().get() : nullptr;
}

template <>
const reco::Track* LeptonBFieldTableProducer<pat::Electron>::getTrack(const pat::Electron& ele) const {
    return ele.gsfTrack().isNonnull() ? ele.gsfTrack().get() : nullptr;
}

typedef LeptonBFieldTableProducer<pat::Muon>     MuonBFieldTableProducer;
typedef LeptonBFieldTableProducer<pat::Electron> ElectronBFieldTableProducer;

DEFINE_FWK_MODULE(MuonBFieldTableProducer);
DEFINE_FWK_MODULE(ElectronBFieldTableProducer);
